#!/usr/bin/env python3

# input: <something><prefix><sql><infix><params><suffix>
# output: <sql_params>;

import sys

logname = sys.argv[1]
sqlname = '{}.sql'.format(logname)
prefix = '[SQL: \''
infix = '\'] [parameters: ('
suffix = ')]'
with open(logname) as logfile, open(sqlname, mode='w') as sqlfile:
	while True:
		line = logfile.readline()
		if not line:
			break
		pref = line.find(prefix)
		inf = line.find(infix)
		suf = line.find(suffix)
		if -1 not in [pref, inf, suf]:
			sql = line[pref+len(prefix):inf]
			params = line[inf+len(infix):suf]
			sql = sql.replace('?', '{}')
			params = ['NULL' if p=='None' else p for p in params.split(', ')]
			sql_params = sql.format(*params)
			sqlfile.write('{};\n'.format(sql_params))
		elif 'ERROR' in line or 'CRITICAL' in line:
			sys.stderr.write(line)
