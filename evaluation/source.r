#!/usr/bin/env Rscript

library(DBI)
library(ggplot2)

read_db <- function(path) {
	# Open raw_peersbase connection
	con <- dbConnect(RSQLite::SQLite(), path)
	# Disable auto commit
	dbBegin(con)
	# Read request table
	sql <- "SELECT timestamp, source, received_peers, duplicate_peers FROM request"
	requests <- dbGetQuery(con, sql)
	# Close database connection
	dbDisconnect(con)
	# Combine tables
	ret <- list(requests)
	# Return result
	return(ret)
}

# Read database
args <- commandArgs(trailingOnly=TRUE)
ret <- read_db(args[1])
requests <- ret[[1]]

# Prepare data
print(head(requests))



print("*** End ***")
