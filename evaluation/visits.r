#!/usr/bin/env Rscript

library(DBI)
library(ggplot2)
library(plyr)

read_db <- function(path, torrent_set) {
	# Open raw_peersbase connection
	con <- dbConnect(RSQLite::SQLite(), path)
	# Disable auto commit
	dbBegin(con)
	# Read peer table
	sql <- "SELECT visits, source FROM peer"
	visits <- dbGetQuery(con, sql)
	# Close database connection
	dbDisconnect(con)
	# Combine tables
	ret <- list(visits)
	# Return result
	return(ret)
}

# Read database
args <- commandArgs(trailingOnly=TRUE)
ret <- read_db(args[1])
visits <- ret[[1]]

# Prepare data
print(head(visits))
visits$type <- ifelse(visits$source=="incoming", "incoming", "outgoing")
visits$source <- NULL
visits <- count(visits)
visits <- visits[visits$visits<=20,]

# Create file
outfile = sub(".sqlite", "_visits.pdf", args[1])
stopifnot(outfile != args[1])
pdf(outfile, width=10, height=3)

# Plot with ggplot2
print(
	ggplot(visits, aes(x=factor(visits), y=freq, fill=type)) + 
	geom_bar(stat="identity", position="dodge") +
	labs(x="Visits", y="Peers")
)
print(paste("Plot written to", outfile))
print("*** End ***")
