import re
import sys
import os
import time
import datetime
import socket

def valid_email(email: str) -> bool:
    atom = r"[0-9a-zA-Z]+[0-9a-zA-Z-]*"
    sub_domain = r"([0-9a-zA-Z]+[0-9a-zA-Z-]*[0-9a-zA-Z]+|[0-9a-zA-Z]+)"
    ip_part = r"([0-9]|[0-9][0-9]|[01][0-9][0-9]|[0-2][0-4][0-9]|[0-2]5[0-5])"
    address_literal = rf"{ip_part}[.]{ip_part}[.]{ip_part}[.]{ip_part}"
    domain = rf"({sub_domain}[.]{sub_domain}|{address_literal})"
    dot_string = rf"({atom}|{atom}[.]{atom})"
    mailbox = dot_string + r"@" + domain

    valid_email = re.compile(r"<" + mailbox + r">")
    if valid_email.fullmatch(email) == None:
        return False
    return True


def read_config_file(config_path: str, get_server_port: bool, get_client_port: bool, path_name: str) -> tuple[int, int, str]:
    # opening file and reading lines
    contents = []
    try:
        with open(config_path) as f:
            contents = f.readlines()
    except FileNotFoundError:
        sys.exit(1)

    # getting server port and send path lines
    server_port_line = ''
    client_port_line = ''
    path_line = ''
    SERVER_PORT = 0
    CLIENT_PORT = 0

    for line in contents:
        if line.startswith('server_port'):
            server_port_line = line.strip("\n")
        elif line.startswith('client_port'):
            client_port_line = line.strip("\n")
        elif line.startswith(path_name):
            path_line = line.strip("\n")
    
    if path_line == '':
        sys.exit(2)

    if get_server_port:
        if server_port_line == '':
            sys.exit(2)
        try:
            SERVER_PORT = int(server_port_line.split('=')[1])
            if SERVER_PORT < 1025:
                raise ValueError
        except ValueError:
            sys.exit(2)
    
    if get_client_port:
        if client_port_line == '':
            sys.exit(2)
        try:
            CLIENT_PORT = int(client_port_line.split('=')[1])
            if CLIENT_PORT < 1025:
                raise ValueError
        except ValueError:
            sys.exit(2)
    if CLIENT_PORT == SERVER_PORT:
        sys.exit(2)
        
    # extracting send path from line
    PATH = path_line.split("=")[1]
    if PATH[0] == '~':
        PATH = os.path.expanduser(PATH)
    if not os.path.isdir(PATH):
        sys.exit(2)

    return SERVER_PORT, CLIENT_PORT, PATH


def save_email(sender: str, receivers: list, date_line: str, subject: str, data_lines: list, inbox_path: str) -> None:
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
    with open(f"{inbox_path}/{filename}.txt", 'w') as f:
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


def setup_server_connection(PORT: int) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('127.0.0.1', PORT))
    return sock

def setup_client_connection(PORT: int, error_msg: str) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.settimeout(20)

    try:
        sock.connect(('127.0.0.1', PORT))
    except (TimeoutError, ConnectionRefusedError):
        print(error_msg, flush=True)
        sys.exit(3)
    return sock

def reset_values():
    return '', [], '', '', []