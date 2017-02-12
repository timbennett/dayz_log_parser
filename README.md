# DayZ Log File Parser
Extracts injury and kill data from DayZ .ADM/.clog log files. 

**Requirements:** [Pandas](http://pandas.pydata.org/) (pip install pandas). Works on Python 2 and 3.

**Usage:** python attack_parser.py *name_of_log.clog*

**Output:**

* injuries_name_of_log.csv: A timestamped list of player-on-player violence.
* kills_name_of_log.csv: A timestamped list of player-caused kills. 

**Discussion:**

My innovation over other log parsers is to detect when a player dies by blood loss, and guesstimate whether that blood loss was due to another player. With direct kills (e.g. headshots) you get a log line like:

    Player "Alice"(id=76561190000000001) has been killed by player "Bob"(id=76561190000000002)
    
But if Bob causes Alice to bleed out, you'll only get this:

    "Alice(uid=76561190000000001) DIED Blood <= 0"
    
So after Bob injures Alice, the script starts a timer. If Alice dies of blood loss within 300 seconds, Bob gets credit for the kill. (This is a trade-off because she might take longer than 300 seconds to die, though this is unusual, and also increases the risk of crediting Bob for a kill when Alice escapes but is attacked and killed by a zombie instead.)

Please let me know if you find this useful or would like to extract other intelligence from your server log files.
