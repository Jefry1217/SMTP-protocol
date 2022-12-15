import sys
import os
import socket
import re
import hmac
import datetime
import time
import base64
import hashlib
import string
import secrets
import methods

SECRET = '928c9bbd3ea5298642cc3e82d3d122e2'

def main():
    if len(sys.argv) != 2:
        sys.exit(1) 
    config_path = sys.argv[1]
    SERVER_PORT, CLIENT_PORT, INBOX_PATH = methods.read_config_file(config_path, True, False, 'inbox_path')
    try:
        sock = methods.setup_server_connection(SERVER_PORT)
    except:
        sys.exit(2)

    while True:
        sock.listen()
        conn, addr = sock.accept()
        emails = receive_from_client(conn)
        conn.close()
        for data in emails[0]:
            methods.save_email(data[0], data[1], data[2], data[3], data[4], INBOX_PATH)
        if emails[1]: 
            break
    sock.close()
    sys.exit(0)

def send(conn, string, end="\r\n"):
    conn.sendall((string + end).encode('ascii'))
    if '\r\n' in string:
        strings = string.split('\r\n')
        print(f'S: {strings[0]}\r\nS: {strings[1]}\r', flush=True)
    else:
        print(f'S: {string}\r', flush=True)

def receive(conn):
    try:
        data = conn.recv(1024).decode().strip('\r\n')
        if data == '':
            raise BrokenPipeError
        print(f'C: {data}\r', flush=True)
        return data
    except:
        raise BrokenPipeError

def get_options(state):
    always_options = ['EHLO', 'RSET', 'NOOP', 'QUIT']
    state_and_options = {
        1 : [],
        3 : ['AUTH', 'MAIL'], # maybe only auth valid here?
        5 : [], # valid authentication data
        7 : [], # do this later, state 7 is what??
        9 : ['RCPT'],
        11 : ['RCPT', 'DATA'],
        13 : ['.']
    }
    return state_and_options[state] + always_options

def receive_from_client(conn):
    emails = []
    send(conn, "220 Service ready")
    state = 1
    all_options = ['EHLO', 'RSET', 'NOOP', 'QUIT',
                    'MAIL', 'AUTH', 'DATA', 'RCPT']
    sender, receivers, date_line, subject, data_lines = methods.reset_values()
    try:
        while True:
            data = receive(conn)
            options = get_options(state)
            # if state == 3:
            #     options.append('MAIL')
            if state == 5:
                state = 3
                if data == '*':
                    send(conn, "501 Syntax error in parameters or arguments")
                    continue
                decoded = base64.b64decode(data).split()
                if len(decoded) == 2:
                    digest = decoded[1].decode()
                    if digest == challenge_response:
                        send(conn, "235 Authentication successful")
                        state = 3
                        continue
                send(conn, "535 Authentication credentials invalid")
                continue
            if state == 13:
                while data != '.':
                    if data.startswith('Subject: '):
                        subject = data
                    elif data.startswith('Date: '):
                        date_line = data
                    else:
                        data_lines.append(data)
                    send(conn, "354 Start mail input end <CRLF>.<CRLF>")
                    data = receive(conn)
                send(conn, '250 Requested mail action okay completed')
                emails.append((sender, receivers, date_line, subject, data_lines))
                sender, receivers, date_line, subject, data_lines = methods.reset_values()
                state = 3
                continue
            if len(data) < 4:
                send(conn, "500 Syntax error, command unrecognized")
                continue
            if data == 'SIGINT':
                send(conn, "SIGINT received, closing")
                return (emails, True)
            command = data[:4]
            if command not in all_options:
                send(conn, "500 Syntax error, command unrecognized")
                continue
            if command not in options:
                send(conn, "503 Bad sequence of commands")
                state = 3
                continue

            if command == 'EHLO':
                # checking syntax
                parts = data.split()
                if len(parts) != 2:
                    send(conn, "501 Syntax error in parameters or arguments")
                    continue
                numbers = parts[1].split('.')
                if len(numbers) != 4:
                    send(conn, "501 Syntax error in parameters or arguments")
                    continue
                valid_address = True
                for n in numbers:
                    try:
                        if int(n) > 255 or int(n) < 0:
                            raise ValueError
                    except:
                        valid_address = False
                        break
                if not valid_address:
                    send(conn, "501 Syntax error in parameters or arguments")
                    continue
                
                # syntax is good, send correct reply
                sender, receivers, date_line, subject, data_lines = methods.reset_values()
                send(conn, "250 127.0.0.1\r\n250 AUTH CRAM-MD5")
                state = 3
                
            elif command == 'MAIL':
                #check page 15, email ABNF syntax
                if not data.startswith('MAIL FROM:'):
                    send(conn, "501 Syntax error in parameters or arguments")
                    continue
                parts = data.split(':')
                if len(parts) > 2:
                    send(conn, "501 Syntax error in parameters or arguments")
                    continue
                if not methods.valid_email(parts[1]):
                    send(conn, "501 Syntax error in parameters or arguments")
                    continue
                sender = data[10:]
                send(conn, '250 Requested mail action okay completed')
                state = 9
            
            elif command == 'RCPT':
                if not data.startswith('RCPT TO:'):
                    send(conn, "501 Syntax error in parameters or arguments")
                    continue
                parts = data.split(':')
                if len(parts) > 2:
                    send(conn, "501 Syntax error in parameters or arguments")
                    continue
                if not methods.valid_email(parts[1]):
                    send(conn, "501 Syntax error in parameters or arguments")
                    continue
                receivers.append(data[8:])
                send(conn, '250 Requested mail action okay completed')
                state = 11
            
            elif command == 'DATA':
                if data != 'DATA':
                    send(conn, "501 Syntax error in parameters or arguments")
                    continue
                send(conn, "354 Start mail input end <CRLF>.<CRLF>")
                state = 13

            elif command == 'NOOP':
                if data != 'NOOP':
                    send(conn, "501 Syntax error in parameters or arguments")
                    continue
                send(conn, '250 Requested mail action okay completed')
            
            elif command == 'AUTH':
                if data != 'AUTH CRAM-MD5':
                    send(conn, '504 Unrecognized authentication type')
                    continue
                alphabet = string.ascii_letters + string.digits
                challenge = ''.join(secrets.choice(alphabet) for i in range(32))
                challenge = challenge.encode('ascii')
                send(conn, '334 ' + base64.b64encode(challenge).decode())
                challenge_response = hmac.new(SECRET.encode(), challenge, hashlib.md5).hexdigest()
                state = 5

            elif command == 'QUIT':
                if data != 'QUIT':
                    send(conn, "501 Syntax error in parameters or arguments")
                    continue
                send(conn, '221 Service closing transmission channel')
                return (emails, False)

            elif command == 'RSET':
                if data != 'RSET':
                    send(conn, '501 Syntax error in parameters or arguments')
                    continue
                sender, receivers, date_line, subject, data_lines= methods.reset_values()
                send(conn, '250 Requested mail action okay completed')
                state = 3
    except (ConnectionResetError, BrokenPipeError) as e:
        print('S: Connection lost\r', flush=True)
        return (emails, False)


if __name__ == "__main__":
    main()