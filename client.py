import socket
import sys
import os
import re
import base64
import hmac
import hashlib
import time
import secrets
import string
import methods


SECRET = '928c9bbd3ea5298642cc3e82d3d122e2'
ID = '9892AC'

def main():
    # checking command line arguments and reading config file
    if len(sys.argv) != 2:
        sys.exit(1)
    config_path = sys.argv[1]
    SERVER_PORT, CLIENT_PORT, PATH = methods.read_config_file(config_path, True, False, 'send_path')

    try:
        send_path_files = os.listdir(PATH)
        send_path_files.sort()
        for i in range(len(send_path_files)):
            send_path_files[i] = PATH + '/' + send_path_files[i]
            send_path_files[i] = send_path_files[i].replace("./","/home/")
        for file_path in send_path_files:
            if os.path.isdir(file_path):
                continue
            with open(file_path) as f:
                f.read()
    except FileNotFoundError as e:
        sys.exit(2)

    # for loop to send all emails
    for email_file in send_path_files:
        # checking email file is of valid type
        email_information = parse_email_contents(email_file)
        if email_information == None:
            print(f'C: {email_file}: Bad formation', flush=True)
            continue

        # establishing client connection
        client_sock = methods.setup_client_connection(SERVER_PORT, 'C: Cannot establish connection')

        send_email_via_server(client_sock, email_information, email_file)
        client_sock.close()
    sys.exit(0)


def check_status_code(client_sock, expected_status_code):
    data = client_sock.recv(1024).decode().strip("\r\n")
    actual_status_code = int(data[:3])
    if actual_status_code == 421:
        print(f'S: {data}\r', flush=True)
        sys.exit(3)
    if actual_status_code != expected_status_code:
        print(f'C: Cannot establish connection', flush=True)
        sys.exit(3)
    if '\r\n' in data:
        strings = data.split('\r\n')
        print(f'S: {strings[0]}\r', flush = True)
        print(f'S: {strings[1]}\r', flush = True)
        return True
    print(f'S: {data}\r', flush=True)
    if actual_status_code == 334:
        return data.split()[1]

def complete_challenge(client_sock, data):
    challenge = base64.b64decode(data).decode('ascii').encode()
    HMAC = hmac.new(SECRET.encode(), challenge, hashlib.md5)
    send(client_sock, (base64.b64encode(('Bobbyboy ' + HMAC.hexdigest()).encode())).decode())

def send(client_sock, string, end='\r\n'):
    client_sock.send((string + end).encode())
    print(f'C: {string}\r', flush=True)

def send_email_via_server(client_sock, email_information, email_name):
    try:
        check_status_code(client_sock, 220)

        send(client_sock, 'EHLO 127.0.0.1')
        if check_status_code(client_sock, 250) != None and 'auth' in email_name.lower():
            send(client_sock, 'AUTH CRAM-MD5')
            data = check_status_code(client_sock, 334)
            complete_challenge(client_sock, data)
            check_status_code(client_sock, 235)

        send(client_sock, f'MAIL FROM:{email_information[0]}')
        check_status_code(client_sock, 250)

        for receiver in email_information[1]:
            send(client_sock, f"RCPT TO:{receiver}")
            check_status_code(client_sock, 250)
        
        send(client_sock, 'DATA')
        check_status_code(client_sock, 354)
        send(client_sock, email_information[2])
        check_status_code(client_sock, 354)
        send(client_sock, f'Subject: {email_information[3]}')
        check_status_code(client_sock, 354)
        for line in email_information[4]:
            send(client_sock, line)
            check_status_code(client_sock, 354)
        send(client_sock, '.')
        check_status_code(client_sock, 250)

        send(client_sock, 'QUIT')
        check_status_code(client_sock, 221)
    except (ConnectionResetError, BrokenPipeError):
        print('C: Connection lost', flush=True)
        sys.exit(3)

def parse_email_contents(email_file):
    # get all components of email
    try:
        with open(email_file) as f:
            sender_line = f.readline().strip("\n")
            receiver_line = f.readline().strip("\n")
            date_line = f.readline().strip("\n")
            subject_line = f.readline().strip("\n")
            data_lines = f.readlines()
            for line in data_lines: data_lines[data_lines.index(line)] = line.strip("\n")
    except:
        return None
    
    # check sender line is valid
    sender_line_parts = sender_line.split()
    if sender_line_parts[0] != 'From:':
        return None
    elif not methods.valid_email(sender_line_parts[1]):
        return None
    sender = sender_line_parts[1]
    # check receiver line is valid
    receiver_line_parts = receiver_line.split(",")
    to_and_first_email = receiver_line_parts[0].split()
    if to_and_first_email[0] != 'To:':
        return None
    elif not methods.valid_email(to_and_first_email[1]):
        return None
    receivers = [to_and_first_email[1]]
    if len(receiver_line_parts) > 1:
        for email in receiver_line_parts[1:]:
            if not methods.valid_email(email):
                return None
            receivers.append(email)
    
    # check date line is valid
    valid_days = ['Mon,', 'Tue,', 'Wed,', 'Thu,', 'Fri,', 'Sat,', 'Sun,']
    valid_months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    valid_time_format = re.compile(r"[0-2][0-9]:[0-5][0-9]:[0-5][0-9]")
    def valid_day_of_month(day):
        if len(day) != 2:
            return False
        if day[0] == '0':
            day = day[1]
        try:
            day = int(day)
        except:
            return False
        if day > 31 or day < 1:
            return False
        return True
    def valid_year(year):
        try:
            year = int(year)
        except: 
            return False
        if year < 1900:
            return False
        return True
    def valid_time(time):
        if not valid_time_format.fullmatch(time):
            return False
        if int(time[0]) > 2 and int(time[1]) > 3:
            return False
        return True
    def valid_timezone(timezone):
        if len(timezone) != 5:
            return False
        if timezone[0] != '+' and timezone[0] != '-':
            return False
        try:
            if int(timezone[1:3]) > 12 or int(timezone[3:]) % 50 != 0:
                return False
        except:
            return False
        return True
    date_line_parts = date_line.split()
    if len(date_line_parts) != 7:
        return None
    if date_line_parts[0] != 'Date:' or date_line_parts[1] not in valid_days \
    or not valid_day_of_month(date_line_parts[2]) or date_line_parts[3] not in valid_months \
    or not valid_year(date_line_parts[4]) or not valid_time(date_line_parts[5]) \
    or not valid_timezone(date_line_parts[6]):
        return None

    # check subject line is valid
    if not subject_line.startswith('Subject: ') or len(subject_line) < 10:
        return None
    subject = subject_line[9:]
    
    # check data lines are valid 
    if len(data_lines) == 0:
        return None
    if len(data_lines) == 1 and len(data_lines[0]) == 0:
        return None
    data = ''
    for i in range(len(data_lines)):
        data_lines[i].strip("\n")
    return (sender, receivers, date_line, subject, data_lines)

if __name__ == "__main__":
    main()