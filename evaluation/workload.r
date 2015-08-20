#!/usr/bin/env Rscript

library(DBI)
library(ggplot2)

read_db <- function(path) {
	# Open raw_peersbase connection
	con <- dbConnect(RSQLite::SQLite(), path)
	# Disable auto commit
	dbBegin(con)
	# Read peer table
	sql <- "SELECT timestamp, thread_workload, load_average FROM statistic"
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

normalize_loadavg <- function(load_average, cores) {
	# Devide by number of cores
	return(load_average/cores)
}

merge_columns <- function(statistic) {
	# Construct time-value dataframe with type column
	return(rbind(
		data.frame(time=statistic$timestamp, value=statistic$thread_workload, type="thread workload"),
		data.frame(time=statistic$timestamp, value=statistic$load_average, type="load average")
	))
}

# Read database
args <- commandArgs(trailingOnly=TRUE)
ret <- read_db(args[1])
statistic <- ret[[1]]

# Prepare data
print(head(statistic))
print("*** Parse timesamps ***")
statistic$timestamp <- parse_timestamps(statistic$timestamp)
print(head(statistic))
print("*** Normalize load average ***")
statistic$load_average <- normalize_loadavg(statistic$load_average, 2)
print(head(statistic))
print("*** Merge columns ***")
statistic <- merge_columns(statistic)
print(head(statistic))

# Create file
outfile = sub(".sqlite", "_workload.pdf", args[1])
stopifnot(outfile != args[1])
pdf(outfile, width=9, height=3)

# Plot with ggplot2
print(
	ggplot(data=statistic, aes(x=time, y=value, group=type, colour=type)) +
    geom_line() +
    geom_point() +
    ylim(0, 1) +
	labs(x="Time UTC", y=NULL)
)
print(paste("Plot written to", outfile))
print("*** End ***")
