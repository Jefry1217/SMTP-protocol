import socket
import os
import sys
import time
import datetime
import methods

def main():
    if len(sys.argv) != 2:
        sys.exit(1)
    config_path = sys.argv[1]
    SERVER_PORT, CLIENT_PORT, SPY_PATH = methods.read_config_file(config_path, True, True, 'spy_path')
    try:
        as_sock = methods.setup_server_connection(CLIENT_PORT) 
    except:
        print('AC: Cannot establish connection', flush=True)
        sys.exit(3)

    while True:
        as_sock.listen()
        conn, addr = as_sock.accept()
        ac_sock = methods.setup_client_connection(SERVER_PORT, 'AS: Cannot establish connection')
        emails = relay_messages(conn, ac_sock, as_sock, SERVER_PORT)
        conn.close()
        for data in emails[0]:
            sender = data[0][10:]
            i = 1
            receivers = []
            while data[i].startswith('RCPT TO:'):
                receivers.append(data[i][8:])
                i += 1
            date_line = data[i]
            i += 1
            subject = data[i]
            i += 1
            data_lines = []
            while i < len(data):
                data_lines.append(data[i])
                i += 1
            methods.save_email(sender, receivers, date_line, subject, data_lines, SPY_PATH)
        if emails[1]:
            break
    as_sock.close()
    sys.exit(0)

def as_send(conn, string, end = '\r\n'):
    conn.send((string + end).encode())
    if '\r\n' in string:
        strings = string.split('\r\n')
        print(f'AC: {strings[0]}\r\nAC: {strings[1]}\r', flush=True)
    else:
        print(f'AC: {string}\r', flush=True)

def as_receive(conn):
    data = conn.recv(1024).decode().strip("\r\n")
    print(f'C: {data}\r', flush=True)
    return data

def ac_send(ac_sock, string, end = '\r\n'):
    ac_sock.send((string + end).encode())
    print(f'AS: {string}\r', flush=True)

def ac_receive(ac_sock):
    codes = [250, 354, 221]
    data = ac_sock.recv(1024).decode().strip("\r\n")
    if '\r\n' in data:
        strings = data.split('\r\n')
        print(f'S: {strings[0]}\r\nS: {strings[1]}\r', flush=True)
    else:
        print(f'S: {data}\r', flush=True)
    try:
        if int(data[:3]) in codes:
            return data, True
        else:
            raise Exception
    except:
        return data, False

def relay_messages(conn, ac_sock, as_sock, SERVER_PORT):
    emails = []
    useful_things = []
    sender, receivers, date_line, subject, data_lines = methods.reset_values()
    from_client = 'a'
    while True:
        try:
            data, is_useful = ac_receive(ac_sock)
            if data == 'SIGINT':
                as_send(conn, data)
                return (emails, True)
            if is_useful:
                if from_client == 'QUIT':
                    as_send(conn, data)
                    return (emails, False)
                if from_client == '.':
                    emails.append((useful_things))
                    useful_things = []
                elif from_client.startswith('EHLO'):
                    useful_things = []
                elif from_client != 'DATA':
                    useful_things.append(from_client)

            as_send(conn, data)
            from_client = as_receive(conn)
            ac_send(ac_sock, from_client)
        except:
            print('AC: Connection lost', flush=True)
            ac_sock.close()
            return emails, False


if __name__ == "__main__":
    main()