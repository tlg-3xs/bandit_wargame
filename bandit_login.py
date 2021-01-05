#!/usr/bin/env python3
import pexpect
import argparse
from os.path import expanduser, join, isfile
import requests
from bs4 import BeautifulSoup as BS

login_prompt = "bandit.+@.*password:"
passwd_file = join(expanduser('~'), 'bandit')
url = 'https://overthewire.org/wargames/bandit/bandit{}.html'

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--passwd-file', dest='passwd_file', default=passwd_file,
            help=f"Path to file with users and passwords. Default: {passwd_file}")
    group=parser.add_mutually_exclusive_group()
    group.add_argument('-f', '--sftp', dest='sftp', action='store_true', default=False,
            help="Switch to sftp instead of ssh")
    group.add_argument('-c', '--commands', dest='cmd', type=str, default='',
            help="Commands to execute instead of login. Like: ssh user@host 'command'")
    group=parser.add_mutually_exclusive_group()
    group.add_argument('level', type=int, nargs='?', help="Numeric level to access.")
    group.add_argument('-l', '--last', action='store_true', default=False, help="Login to last level solved.")
    group=parser.add_mutually_exclusive_group()
    group.add_argument('-p', '--password', dest='passwd', nargs='?', help="Password to log in")
    group.add_argument('-i', '--identity-file', dest='key', nargs='?', help="SSH key to log in")
    return parser.parse_args()

def read_file(args):
    if not isfile(args.passwd_file):  # Si no se encuentra el archivo, se crea uno con el nivel inicial
        with open(args.passwd_file, 'w') as f:
            initial_level = "bandit0 bandit0\n"
            f.write(initial_level)
        return [initial_level]
    with open(args.passwd_file, 'r') as f:
        lines = f.readlines()
    return lines

def get_last(args):
    lines = read_file(args)
    maximo = 0
    for line in lines:
        number = int(line.split()[0].replace('bandit', ''))
        maximo = number if number > maximo else maximo
    return maximo

def get_pass(args):
    for line in read_file(args):
        user, passwd = line.strip().split()
        if user == f'bandit{args.level}':
            return passwd

def write_pass(args):
    lines = read_file(args);
    for line in lines:
        user, password = line.strip().split()
        if user == f'bandit{args.level}':
            return
    with open(args.passwd_file, 'a') as f:
        f.write(f'bandit{args.level} {args.passwd}\n')


def get_mission(args):
    r = requests.get(url.format(args.level + 1))
    soup = BS(r.content, features="html.parser")
    return soup.find('div', {"id": "content"}).text.strip()


def main():
    args = parse_args()

    if args.last or args.level is None:
        args.level = get_last(args)
    
    if args.key is None and args.passwd is None:
        passwd = get_pass(args)
        if not passwd:
            print(f"Password for bandit{args.level} not found in {args.passwd_file}")
            return
        else:
            args.passwd = passwd
    
    command_list = ['alias ll="ls -lahF"', f'alias get_cpw="cat /etc/bandit_pass/bandit{args.level}"']
    cmd = 'sftp' if args.sftp else 'ssh'
    shell_prompt = 'bandit[0-9]+@bandit:.*\$' if not args.sftp else 'sftp>'
    
    if args.key:
        p = pexpect.spawn(f"{cmd} -i '{args.key}' bandit{args.level}@bandit" if not args.cmd else f"{cmd} -i '{args.key}' bandit{args.level}@bandit '{args.cmd}'")
    else:
        p = pexpect.spawn(f"{cmd} bandit{args.level}@bandit" if not args.cmd else f"{cmd} bandit{args.level}@bandit '{args.cmd}'")
    
    if args.passwd:
        p.expect(login_prompt)
        p.sendline(args.passwd)
    
    index = p.expect([shell_prompt, login_prompt, pexpect.EOF, pexpect.TIMEOUT], timeout=5)
    
    if index == 1:  # Ha devuelto otra vez el prompt de login, lo que significa que la contraseña es incorrecta
        print(f"Incorrect bandit{args.level} password!")
        return
    
    # Pasado este punto, se entiende que la contraseña es correcta y se procede a escribirla
    
    if args.passwd:
        write_pass(args)
    
    if index == 2: # Si se cierra de golpe la sesión, muestra todo el output
        print(p.before.decode())
        return
    if not args.sftp and index == 0:  # Si encuentra un prompt de shell (y no es sftp), ejecuta los alias
        for alias in command_list:
            p.sendline(alias)
            p.expect(shell_prompt)
    print("Mission:", get_mission(args), sep='\n\n', end='\n\n')
    p.sendline('')  # Para imprimir el prompt, se manda una linea en blanco (como si se hubiera dado a enter)
    p.expect('')    # Y hace un expect vacío, para no consumir el buffer y que al hacer interact, imprima el prompt
    p.interact()
    p.close()

if __name__=='__main__':
    main()
