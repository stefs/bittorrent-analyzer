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
visits_c <- count(visits)
visits_c <- visits_c[visits_c$visits<=20,]
print(summary(visits))
print(summary(visits_c))

# Create file
outfile = sub(".sqlite", "_visits.pdf", args[1])
stopifnot(outfile != args[1])
pdf(outfile, width=9, height=2.8)

# Plot with ggplot2
print(
	ggplot(visits_c, aes(x=factor(visits), y=freq, fill=source)) +
	geom_bar(stat="identity", position="dodge") +
	labs(x="Visits", y="Peers")
)
print(
	ggplot(visits, aes(x=visits, colour=source)) +
	stat_ecdf(size=1) +
	scale_x_continuous(breaks=10^(0:3)) +
	coord_trans(x = "log10", limx=c(1, 1000)) +
	labs(x="Visits", y="CDF of Peers")
)
print(paste("Plot written to", outfile))
print("*** End ***")
