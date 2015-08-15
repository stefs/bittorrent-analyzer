#!/usr/bin/env Rscript

library(DBI)
library(ggplot2)

read_db <- function(path) {
	# Open raw_peersbase connection
	con <- dbConnect(RSQLite::SQLite(), path)
	# Disable auto commit
	dbBegin(con)
	# Read request table
	sql <- "SELECT timestamp, source, received_peers, duplicate_peers, torrent FROM request"
	request <- dbGetQuery(con, sql)
	# Close database connection
	dbDisconnect(con)
	# Combine tables
	ret <- list(request)
	# Return result
	return(ret)
}

hour_timestamps <- function(timestamps) {
	# Parse timestamps
	timestamps <- as.POSIXct(timestamps, tz="GMT", origin="1960-01-01")
	# Truncate to hours
	timestamps <- trunc(timestamps, units="hours")
	# Revert to strings
	timestamps <- as.character(timestamps)
	# Return result
	return(timestamps)
}

aggregate_time <- function(request) {
	# Aggregate by torrent id and last seen
	values_df <- data.frame(total=request$received_peers, duplicate=request$duplicate_peers)
	groups <- list(group_hour=request$timestamp, group_source=request$source, group_torrent=request$torrent)
	ret <- aggregate(values_df, by=groups, FUN=sum)
	# Return result
	return(ret)
}

# Read database
args <- commandArgs(trailingOnly=TRUE)
ret <- read_db(args[1])
request <- ret[[1]]

# Prepare data
print(head(request))
print("*** Parse timesamps ***")
request$timestamp <- hour_timestamps(request$timestamp)
print(head(request))
print("*** Aggregate timestamp ***")
request <- aggregate_time(request)
print(head(request))

# Data per torrent
outfile = sub(".sqlite", "_source.pdf", args[1])
stopifnot(outfile != args[1])
pdf(outfile, width=9, height=6)
#for (torrent in unique(downloads$group_torrent)) {
#	# Get torrent name
#	info <- torrents[torrents$id==torrent,]
#	name <- strtrim(info$display_name, 50)
#	size <- round(info$gigabytes, digits=1)
#	description <- paste("Torrent ", torrent, ": \"", name, "\" (", size, " GB)", sep="")
#	print(description)

#	# Scrape data
#	filtered <- filter_request(request, torrent)
#	if (nrow(filtered) == 0) {
#		print("No scrape data")
#		scrape <- data.frame(group_hour=NA, downloads=NA)
#	} else {
#		scrape <- aggregate_complete(filtered)
#	}
#	print(scrape)

#	# Confirmed data
#	confirmed <- filter_download(downloads, torrent)
#	print(confirmed)

#	# Merge on timestamp
#	scrape$category <- "scrape"
#	confirmed$category <- "confirmed"
#	total <- rbind(scrape, confirmed)
#	total <- total[complete.cases(total$group_hour),]
#	print(total)

#	# Plot with ggplot2
#	print(
#		ggplot(total, aes(factor(total$group_hour), downloads, fill=category)) +
#		geom_bar(stat="identity", position="dodge") +
#		theme(axis.text.x=element_text(angle=90, hjust=1)) +
#		labs(title=description, x="Time UTC", y="Downloads")
#	)
#}
#print(paste("Plot written to", outfile))
print("*** End ***")
