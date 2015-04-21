#!/usr/bin/env Rscript

# Import packet with error on failure
library(DBI)

# Open mydatabase connection
con <- dbConnect(RSQLite::SQLite(), "output/2015-04-16_11-26-46_faui1-246.sqlite")

# Disable auto commit
dbBegin(con)

# Get total pieces
total_pieces <- dbGetQuery(con, "SELECT id, pieces_count FROM torrent")

# Get example mydata
res <- dbSendQuery(con, "SELECT first_pieces, last_pieces, last_seen, torrent FROM peer")
mydata <- dbFetch(res, n=5)
dbClearResult(res)
print("*** Input ***")
print(mydata)

# Filter for first torrent, debug
mydata <- mydata[mydata$torrent==1,]

# Filter for usable last pieces
mydata <- mydata[complete.cases(mydata$last_pieces),]

# Add pieces delta, drop absolute pieces, filter for positive delta
mydata$pieces_delta <- mydata$last_pieces - mydata$first_pieces
mydata$first_pieces <- NULL
mydata$last_pieces <- NULL
mydata <- mydata[mydata$pieces_delta>0,]

# Parse timestamps and truncate to hours
mydata$last_seen <- as.POSIXct(mydata$last_seen, tz="GMT")
mydata$last_seen <- trunc(mydata$last_seen, units="hours")
print("*** Processed ***")
print(mydata)

# TODO
print("*** Aggregated ***")
aggregate(last_seen ~ pieces_delta, mydata, sum)

# Disconnect from the mydatabase
dbDisconnect(con)

# Indicate complete execution of script
print("Finished")

