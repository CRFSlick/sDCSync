import subprocess
import binascii
import argparse
import base64
import glob
import sys
import re
import os

default_path = '/volume*/@appstore/DirectoryServerForWindowsDomain/private'
default_output = 'output.dat'
stderr = open(os.devnull, 'w')

parser = argparse.ArgumentParser()
parser.add_argument('--path', type=str, nargs='?', const=True, metavar='directory', help='specify location of private ldap data folder (default: /volume*/@appstore/DirectoryServerForWindowsDomain/private/)')
parser.add_argument('--output', type=str, nargs='?', const=True, metavar='output file', help='output file name and location')
args = parser.parse_args()

if args.output:
	default_output = args.output

def cmd(cmd):
	# Python 2.7 backwards compatibility
	sys.stdout.write('[*] Running command... ')
	sys.stdout.flush()
	result = subprocess.check_output(cmd, shell=True, stderr=stderr).decode('utf-8')
	print('Done!')
	return result

def dump_hashes(path=None):
	if not path:
		path = default_path

	if not glob.glob(path):
		if path == default_path:
			print('[-] Default path \"' + path + '\" does not exist')
			parser.print_help()
		else:
			print('Error: Path \"' + path + '\" does not exist')
		exit()

	command = 'ldbsearch -H ' + path + '/sam.ldb unicodepwd'
	try:
		output = ''
		for record in cmd(command).split('# record '):
			if 'unicodePwd' in record:
				entries = record.split('\n')
				entries = [entries[1], entries[2]]
				username = re.findall('CN=(.*?),.*', entries[0])[0]
				NTLM_hash = binascii.hexlify(base64.b64decode(re.findall('unicodePwd:: (.*)', entries[1])[0])).decode('utf-8')
				output += username + ':' + NTLM_hash + '\n'
		print('[*] Writing output to "' + default_output + '"')
		with open(default_output, 'w') as output_file:
			output_file.write(output)
			output_file.close()
	except subprocess.CalledProcessError:
		print('Error!')
		print('[!] It seems that running \"' + command.split(' ')[0] + '\" has failed, resorting to manual extraction.')
		
		# Dependencies of manual enum, avoid if not needed
		import samba
		import ldb

		path += '*'

		folders = glob.glob(path)
		for folder in folders:
			if not os.access(folder, os.R_OK) or not os.access(folder + '/sam.ldb.d/', os.R_OK):
				print('[-] Permission error, please run as sudo!')
				exit()
			try:
				files = os.listdir(folder + '/sam.ldb.d/')
			except:
				if len(folders) > 1:
					print('[!] Invalid folder "' + folder + '", skipping...')
					continue
				else:
					print('[-] Invalid folder "' + folder + '", could not find "/sam.ldb.d/"')
					exit()
			for file in files:
				if re.findall('^(DC=[^,]*?),(DC=[^,]*?).ldb', file):
					db = samba.Ldb(folder + '/sam.ldb.d/' + file)
					data = db.search(base=ldb.Dn(db, file.strip('.ldb')))
					output = ''

					for obj in data:
						try:
							username = str(obj['sAMAccountName']).split('@')[0]
							unicodepwd_raw = obj['unicodePwd']
							unicodepwd = ''
							for byte in unicodepwd_raw:
								unicodepwd += byte.hex()
							output += str(username) + ':' + str(unicodepwd) + '\n'
						except KeyError:
							pass
					print('[*] Writing output to "' + default_output + '"')
					with open(default_output, 'w') as output_file:
						output_file.write(output)
						output_file.close()

def main():
	print('-+= CRFSlick\'s Synology Directory Server Hash Extractor =+-')
	dump_hashes(args.path)
	print('[+] Success!')

main()
