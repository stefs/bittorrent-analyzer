#!/usr/bin/env Rscript

library(DBI)
library(ggplot2)
library(reshape)

read_db <- function(path) {
	# Open raw_peersbase connection
	con <- dbConnect(RSQLite::SQLite(), path)
	# Disable auto commit
	dbBegin(con)
	# Read peer table
	sql <- "SELECT timestamp, thread_workload, evaluator_threads, server_threads, memory_mb, load_average, peer_queue, visited_queue FROM statistic"
	statistic <- dbGetQuery(con, sql)
	# Close database connection
	dbDisconnect(con)
	# Combine tables
	ret <- list(statistic)
	# Return result
	return(ret)
}

parse_timestamps <- function(timestamps) {
	# Parse timestamps
	timestamps <- as.POSIXct(timestamps, tz="GMT", origin="1970-01-01")
	# Return result
	return(timestamps)
}

merge_columns <- function(statistic) {
	# Construct timestamp-value dataframe with variable column
	return(melt(statistic, id=c("timestamp")))
}

# Read database
args <- commandArgs(trailingOnly=TRUE)
ret <- read_db(args[1])
statistic <- ret[[1]]

# Prepare data
print(head(statistic))
print("*** Merge columns ***")
statistic <- merge_columns(statistic)
print(statistic)
print("*** Parse timesamps ***")
statistic$timestamp <- parse_timestamps(statistic$timestamp)
print(head(statistic))

# Create file
outfile = sub(".sqlite", "_workload.pdf", args[1])
stopifnot(outfile != args[1])
pdf(outfile, width=9, height=9)

# Plot with ggplot2
print(
	ggplot(data=statistic, aes(x=timestamp, y=value, group=variable)) +
    geom_line() +
    geom_point() +
    facet_grid(variable ~ ., scales="free_y") +
    ylim(0, NA) +
	labs(x="Time UTC", y=NULL) +
	theme(legend.position="none")
)
print(paste("Plot written to", outfile))
print("*** End ***")
