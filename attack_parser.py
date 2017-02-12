import re
import time
import datetime
from datetime import timedelta
import pandas as pd
import sys
import csv
#import gzip # use gzip if you're reading a zipped log file

# Search patterns
# courtesy of https://github.com/C222/DayZ-Obituaries/blob/master/regex_parse.py
kill =       '((?:(?:[0-1][0-9])|(?:[2][0-3])|(?:[0-9])):(?:[0-5][0-9])(?::[0-5][0-9])?(?:\\s?(?:am|AM|pm|PM))?).*?Player.*?(".*?").*?id=(\\d+).*?has been killed by.*?player.*?(".*?").*?id=(\\d+)'
day =        'AdminLog started on ((?:(?:[1]{1}\\d{1}\\d{1}\\d{1})|(?:[2]{1}\\d{3}))[-:\\/.](?:[0]?[1-9]|[1][012])[-:\\/.](?:(?:[0-2]?\\d{1})|(?:[3][01]{1})))(?![\\d]) at ((?:(?:[0-1][0-9])|(?:[2][0-3])|(?:[0-9])):(?:[0-5][0-9])(?::[0-5][0-9])?(?:\\s?(?:am|AM|pm|PM))?)'
injury =     '((?:(?:[0-1][0-9])|(?:[2][0-3])|(?:[0-9])):(?:[0-5][0-9])(?::[0-5][0-9])?(?:\\s?(?:am|AM|pm|PM))?).*?"(.*?)\\(uid=(\\d+)\\).*?(SHOT|HIT) (.*?)\\(uid=(\\d+)\\) by (.*?) into (.*?)\\."'
timestamp =  '^((?:(?:[0-1][0-9])|(?:[2][0-3])|(?:[0-9])):(?:[0-5][0-9])(?::[0-5][0-9])?(?:\\s?(?:am|AM|pm|PM))?)' 
blood_death ='((?:(?:[0-1][0-9])|(?:[2][0-3])|(?:[0-9])):(?:[0-5][0-9])(?::[0-5][0-9])?(?:\\s?(?:am|AM|pm|PM))?).*?"(.*?)\\(uid=(\\d+)\\) (DIED Blood <= 0\")'
damage =     '((?:(?:[0-1][0-9])|(?:[2][0-3])|(?:[0-9])):(?:[0-5][0-9])(?::[0-5][0-9])?(?:\s?(?:am|AM|pm|PM))?).*?"(.*?)\\(uid=(\\d+)\\) STATUS S::([-\\d\\.]+) B::([-\\d\\.]+) H::([-\\d\\.]+)'

# Compiled regexen
kill_c = re.compile(kill,re.IGNORECASE|re.DOTALL)
day_c = re.compile(day,re.IGNORECASE|re.DOTALL)
injury_c = re.compile(injury,re.IGNORECASE|re.DOTALL)
timestamp_c = re.compile(timestamp,re.IGNORECASE|re.DOTALL)
blood_death_c = re.compile(blood_death,re.IGNORECASE|re.DOTALL)
damage_c = re.compile(damage,re.IGNORECASE|re.DOTALL)

# Tracking variables
last_injury_time = {} # records victim's timestamp and attacker details after each player-inflicted injury

# Output variables
kill_output = [] # contains individual kill event details
injury_output = [] # data related to players' injuries
blood_death_output = [] # deaths from blood loss, not direct damage

# Time related
current_day = ""
current_time = ""

# Functions
def check_increment_date(current_timestamp, this_timestamp):
	'''
	If a log file passes midnight, increment the current_day. Pass it
	current_timestamp and a new timestamp (this_timestamp) and it will
	checks whether this_timestamp is earlier in the 24 hour day than
	current_timestamp; if so, we've gone past midnight (e.g. 23:59:59 > 00:00:00)
	and need to set current_timestamp to this_timestamp + 1 day.
	'''
	if this_timestamp < current_timestamp:
		return this_timestamp + timedelta(days=1)
	else:
		return this_timestamp

lines = [] # we'll read all lines into this list initially


#with gzip.open('zipped_big_log_file.ADM.gz','rb') as f: # remember to also import gzip if you're doing this
with open(sys.argv[1], 'rb') as f:
	# read all lines into the list of lines (personal choice; I find it easier to read previous/subsequent lines this way)
	for line in f:
		lines.append(str(line))
	print("{} lines ingested.".format(len(lines)))

for line_number, line in enumerate(lines):
	# main processing loop examines every line sequentially, deciding if it's one of:
	#	day_line: timestamp on server startup, used to set the day-month-year in timestamps
	#	injury_line: where one player injures another in a body part with a weapon
	#	kill_line: where one player dies and the killer is named
	#	blood_death_line: where a player dies of blood loss and the cause is ambiguous without further investigation
	
	if line_number % 1000 == 0: # progress counter
		print("processed {} lines".format(line_number))

	day_line = day_c.search(line)
	if day_line:
		# construct timestamp from the regex match
		current_day = day_line.group(1)
		current_time = day_line.group(2)
		current_timestamp = datetime.datetime.strptime(current_day+" "+current_time,"%Y-%m-%d %H:%M:%S")

	injury_line = injury_c.search(line)
	if injury_line:
				
		# check if date needs incrementing
		this_timestamp = datetime.datetime.strptime(current_day+" "+injury_line.group(1),"%Y-%m-%d %H:%M:%S")
		current_timestamp = check_increment_date(current_timestamp, this_timestamp)
		
		# Regex groups: 1:"Timestamp",2:"Attacker",3:"Attacker_ID",4:"Attack_type",5:"Victim",6:"Victim_ID",7:"Weapon",8:"Body_part"
		# injury_output will get turned into a dataframe later
		injury_output.append([current_timestamp, 
							  injury_line.group(2),
							  injury_line.group(3),
							  injury_line.group(4),
							  injury_line.group(5),
							  injury_line.group(6),
							  injury_line.group(7),
							  injury_line.group(8).lower() # lower case because eg RightArm and rightarm exist but AFAIK are duplicates;
														   # (however if they refer to upper and lower arm, this would be a wrong decision)
							 ])
		# set the timestamp and perpetrator of the victim_id's most recent injury
		# if they die within 5 minutes from blood loss, the most recent attacker gets credit
		# (this check happens in 'if blood_death_line' conditional below)
		last_injury_time[injury_line.group(6)] = [current_timestamp, injury_line.group(2), injury_line.group(3), injury_line.group(5)]

	kill_line = kill_c.search(line)
	if kill_line:
		this_timestamp = datetime.datetime.strptime(current_day+" "+kill_line.group(1),"%Y-%m-%d %H:%M:%S")
		current_timestamp = check_increment_date(current_timestamp, this_timestamp)
		
		# Regex groups: 1: time 2: victim name, 3:victim id 4:killer name, 5:killer id
		if kill_line.group(3) in last_injury_time: # remove victim from last_injury_time; not needed to determine killer
			del last_injury_time[kill_line.group(3)]
			
		kill_output.append([current_timestamp, 
							kill_line.group(4), 
							kill_line.group(5), 
							kill_line.group(2),
							kill_line.group(3),
							'Direct',
							0
							])
	
	blood_death_line = blood_death_c.search(line)
	if blood_death_line:
		# group 1: timestamp; group 2: victim; group 3: victim_id
		# update the current_timestamp
		this_timestamp = datetime.datetime.strptime(current_day+" "+blood_death_line.group(1),"%Y-%m-%d %H:%M:%S")
		current_timestamp = check_increment_date(current_timestamp, this_timestamp)
		# check if the victim had an injury timer and how long ago it was:        
		if blood_death_line.group(3) in last_injury_time:
			delta = (current_timestamp - last_injury_time[blood_death_line.group(3)][0]).total_seconds() # check how long since the injury occurred
			if delta < 300: 
				# award kill to a killer only if it's within 5 minutes; basically decided to do this
				# as a stopgap because longer windows increase the odds of attributing a zombie attack
				# to another player; this could be avoided by only keeping a player on the last_injury_time list
				# while they are in a bleeding state, but that is possibly complicated by other factors, so this
				# is a compromise value.
				killer = last_injury_time[blood_death_line.group(3)][1]
				killer_id = last_injury_time[blood_death_line.group(3)][2]
				kill_output.append([current_timestamp, 
										   killer, 
										   killer_id, 
										   blood_death_line.group(2), 
										   blood_death_line.group(3), 
										   'Blood loss',
										   delta
										  ])
			#else: # uncomment to do something for deaths as a result of other blood loos
			#    print "{} Bloodloss {} {}".format(current_timestamp,blood_death_line.group(2),delta)
		if blood_death_line.group(3) in last_injury_time: # they're dead; we don't need to track last_injury_time till they're injured again
			del last_injury_time[blood_death_line.group(3)]

# create dataframes for output
injuries_df = pd.DataFrame(injury_output, columns=['Timestamp','Attacker','Attacker_ID','Attack_Type','Victim','Victim_ID','Weapon','Body_Part'])
injuries_df = injuries_df.drop_duplicates() # log files contain frequent multiple entries for a single high-damage attack; this condenses them into one attack
injuries_df[['Attacker_ID','Victim_ID']].apply(str) # this is meant to help when opening output CSVs in Excel... but it still treats quoted numeric strings as numbers :(

kills_df = pd.DataFrame(kill_output, columns=['Timestamp','Killer','Killer_ID','Victim','Victim_ID','Kill type','Elapsed time'])

injuries_df.to_csv("injuries_{}.csv".format(sys.argv[1]),index=False, quoting=csv.QUOTE_NONNUMERIC)
print('Saved "injuries_{}.csv"'.format(sys.argv[1]))
kills_df.to_csv("kills_{}.csv".format(sys.argv[1]),index=False)
print('Saved "kills_{}.csv"'.format(sys.argv[1]))
print('Processing complete.')
