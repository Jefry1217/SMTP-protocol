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
    order = 0
    SERVER_PORT, CLIENT_PORT, PATH = methods.read_config_file(config_path, True, False, 'inbox_path')
    try:
        sock = methods.setup_server_connection(SERVER_PORT)
    except:
        sys.exit(2)
    while True:
        sock.listen()
        conn, addr = sock.accept()
        pid = os.fork()
        order += 1
        order_str = str(order)
        if order < 10:
            order_str = '0' + order_str
        if pid != 0:
            continue
        pid = os.getpid()
        emails = receive_from_client(conn, pid, order_str)
        conn.close()
        sock.close()
        for data in emails[0]:
            save_email(data[0], data[1], data[2], data[3], data[4], PATH, pid, order)
        sys.exit(0)


def send(conn, string, pid, order, end="\r\n"):
    conn.send((string + end).encode())
    if '\r\n' in string:
        strings = string.split('\r\n')
        print(f'[{pid}][{order}]S: {strings[0]}\r\n[{pid}][{order}]S: {strings[1]}\r', flush=True)
    else:
        print(f'[{pid}][{order}]S: {string}\r', flush=True)


def receive(conn, pid, order):
    try:
        data = conn.recv(1024).decode().strip('\r\n')
        if data == '':
            raise BrokenPipeError
        print(f'[{pid}][{order}]C: {data}\r', flush=True)
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

def save_email(sender, receivers, date_line, subject, data_lines, inbox_path, pid, order):
    filename = 'unknown.txt'
    if date_line != '':
        parts = date_line.split()
        year = int(parts[4])
        month_str_to_int = {
            'Jan' : 1,
            'Feb' : 2,
            'Mar' : 3,
            'Apr' : 4,
            'May' : 5,
            'Jun' : 6,
            'Jul' : 7,
            'Aug' : 8,
            'Sep' : 9,
            'Oct' : 10,
            'Nov' : 11,
            'Dec' : 12
        }
        month = month_str_to_int[parts[3]]
        def remove_leading_zero(thing):
            if thing[0] == '0':
                thing = thing[1]
            return int(thing)
        day = remove_leading_zero(parts[2])
        hr_min_sec = parts[5].split(':')
        hr = remove_leading_zero(hr_min_sec[0])
        min = remove_leading_zero(hr_min_sec[1])
        sec = remove_leading_zero(hr_min_sec[2])

        filename = int(time.mktime(datetime.datetime(year, month, day, hr, min, sec).timetuple()))
    with open(f"{inbox_path}/[{pid}][{order}]{filename}.txt", 'w') as f:
        f.write(f'From: {sender}\n')
        f.write('To: ')
        for receiver in receivers:
            f.write(receiver)
            if receivers.index(receiver) != len(receivers) - 1:
                f.write(',')
            else:
                f.write('\n')
        if date_line == '':
            f.write('Date: \n')
        else:
            f.write(date_line + '\n')
        if subject == '':
            f.write('Subject: \n')
        else:
            f.write(subject + '\n')
        for line in data_lines:
            f.write(line + '\n')


def receive_from_client(conn, pid, order):
    emails = []
    send(conn, "220 Service ready", pid, order)
    state = 1
    all_options = ['EHLO', 'RSET', 'NOOP', 'QUIT',
                    'MAIL', 'AUTH', 'DATA', 'RCPT']
    sender, receivers, date_line, subject, data_lines = methods.reset_values()
    completed_auth = False
    try:
        while True:
            data = receive(conn, pid, order)
            options = get_options(state)
            # if data == '':
            #     return emails
            if state == 3 and completed_auth:
                options.append('MAIL')
            if state == 5:
                state = 3
                if data == '*':
                    send(conn, "501 Syntax error in parameters or arguments", pid, order)
                    continue
                decoded = base64.b64decode(data).split()
                if len(decoded) == 2:
                    digest = decoded[1].decode()
                    if digest == challenge_response:
                        send(conn, "235 Authentication successful", pid, order)
                        state = 3
                        continue
                send(conn, "535 Authentical credentials invalid", pid, order)
                continue
            if state == 13:
                while data != '.':
                    if data.startswith('Subject: '):
                        subject = data
                    elif data.startswith('Date: '):
                        date_line = data
                    else:
                        data_lines.append(data)
                    send(conn, "354 Start mail input end <CRLF>.<CRLF>", pid, order)
                    data = receive(conn, pid, order)
                send(conn, '250 Requested mail action okay completed', pid, order)
                emails.append((sender, receivers, date_line, subject, data_lines, completed_auth))
                sender, receivers, date_line, subject, data_lines = methods.reset_values()
                completed_auth = False
                state = 3
                continue
            if len(data) < 4:
                send(conn, "500 Syntax error, command unrecognized", pid, order)
                continue
            if data == 'SIGINT':
                send(conn, "SIGINT received, closing", pid, order)
                return (emails, True)
            command = data[:4]
            if command not in all_options:
                send(conn, "500 Syntax error, command unrecognized", pid, order)
                continue
            if command not in options:
                send(conn, "503 Bad sequence of commands", pid, order)
                state = 3
                continue

            if command == 'EHLO':
                # checking syntax
                parts = data.split()
                if len(parts) != 2:
                    send(conn, "501 Syntax error in parameters or arguments", pid, order)
                    continue
                numbers = parts[1].split('.')
                if len(numbers) != 4:
                    send(conn, "501 Syntax error in parameters or arguments", pid, order)
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
                    send(conn, "501 Syntax error in parameters or arguments", pid, order)
                    continue
                
                # syntax is good, send correct reply
                sender, receivers, date_line, subject, data_lines = methods.reset_values()
                completed_auth = False
                send(conn, "250 127.0.0.1" + '\r\n' + "250 AUTH CRAM-MD5", pid, order)
                state = 3
                
            elif command == 'MAIL':
                #check page 15, email ABNF syntax
                if not data.startswith('MAIL FROM:'):
                    send(conn, "501 Syntax error in parameters or arguments", pid, order)
                    continue
                parts = data.split(':')
                if len(parts) > 2:
                    send(conn, "501 Syntax error in parameters or arguments", pid, order)
                    continue
                if not methods.valid_email(parts[1]):
                    send(conn, "501 Syntax error in parameters or arguments", pid, order)
                    continue
                sender = data[10:]
                send(conn, '250 Requested mail action okay completed', pid, order)
                state = 9
            
            elif command == 'RCPT':
                if not data.startswith('RCPT TO:'):
                    send(conn, "501 Syntax error in parameters or arguments", pid, order)
                    continue
                parts = data.split(':')
                if len(parts) > 2:
                    send(conn, "501 Syntax error in parameters or arguments", pid, order)
                    continue
                if not methods.valid_email(parts[1]):
                    send(conn, "501 Syntax error in parameters or arguments", pid, order)
                    continue
                receivers.append(data[8:])
                send(conn, '250 Requested mail action okay completed', pid, order)
                state = 11
            
            elif command == 'DATA':
                if data != 'DATA':
                    send(conn, "501 Syntax error in parameters or arguments", pid, order)
                    continue
                send(conn, "354 Start mail input end <CRLF>.<CRLF>", pid, order)
                state = 13

            elif command == 'NOOP':
                if data != 'NOOP':
                    send(conn, "501 Syntax error in parameters or arguments", pid, order)
                    continue
                send(conn, '250 Requested mail action okay completed', pid, order)
            
            elif command == 'AUTH':
                if data != 'AUTH CRAM-MD5':
                    send(conn, '504 Unrecognized authentication type', pid, order)
                    continue
                alphabet = string.ascii_letters + string.digits
                challenge = ''.join(secrets.choice(alphabet) for i in range(32))
                challenge = challenge.encode('ascii')
                send(conn, '334 ' + base64.b64encode(challenge).decode(), pid, order)
                challenge_response = hmac.new(SECRET.encode(), challenge, hashlib.md5).hexdigest()
                state = 5

            elif command == 'QUIT':
                if data != 'QUIT':
                    send(conn, "501 Syntax error in parameters or arguments", pid, order)
                    continue
                send(conn, '221 Service closing transmission channel', pid, order)
                return (emails, False)

            elif command == 'RSET':
                if data != 'RSET':
                    send(conn, '501 Syntax error in parameters or arguments', pid, order)
                    continue
                sender, receivers, date_line, subject, data_lines = methods.reset_values()
                completed_auth = False
                send(conn, '250 Requested mail action okay completed', pid, order)
                state = 3

            elif state == 5:
                pass
    except (ConnectionResetError, BrokenPipeError) as e:
        print('S: Connection lost\r', flush=True)
        return (emails, False)

if __name__ == "__main__":
    main()