#!/usr/bin/env Rscript

library(DBI)
library(ggplot2)

read_db <- function(path) {
	# Open raw_peersbase connection
	con <- dbConnect(RSQLite::SQLite(), path)
	# Disable auto commit
	dbBegin(con)
	# Read peer table
	sql <- "SELECT id, first_pieces, last_pieces, last_seen, torrent FROM peer"
	peers <- dbGetQuery(con, sql)
	# Read torrent table
	sql <- "SELECT id, complete_threshold, display_name, pieces_count, piece_size FROM torrent"
	torrents <- dbGetQuery(con, sql)
	# Read request table
	sql <- "SELECT timestamp, completed, torrent FROM request"
	requests <- dbGetQuery(con, sql)
	# Close database connection
	dbDisconnect(con)
	# Combine tables
	ret <- list(peers, torrents, requests)
	# Return result
	return(ret)
}

merge_with_torrents <- function(peers, torrents) {
	# Inner join
	peers <- merge(peers, torrents, by.x="torrent", by.y="id")
	# Return result
	return(peers)
}

filter_peers <- function(peers) {
	# Filter for usable last pieces
	peers <- peers[complete.cases(peers$last_pieces),]
	# Filter according to threshold
	peers <- peers[peers$first_pieces < peers$complete_threshold,]
	peers <- peers[peers$last_pieces >= peers$complete_threshold,]
	# Return result
	return(peers)
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

aggregate_time <- function(peers) {
	# Aggregate by torrent id and last seen
	values_df <- data.frame(downloads=peers$id)
	groups <- list(group_torrent=peers$torrent, group_hour=peers$last_seen)
	ret <- aggregate(values_df, by=groups, FUN=length)
	# Return result
	return(ret)
}

filter_download <- function(downloads, torrent){
	# Extract all rows with that id
	downloads <- downloads[downloads$group_torrent==torrent,]
	# Drop torrend id
	downloads$group_torrent <- NULL
	# Return result
	return(downloads)
}

filter_request <- function(requests, torrent) {
	# Delete rows without complete value
	requests <- requests[complete.cases(requests$completed),]
	# Extract all rows with that id
	requests <- requests[requests$torrent==torrent,]
	# Drop torrend id
	requests$torrent <- NULL
	# Return result
	return(requests)
}

aggregate_complete <- function(requests) {
	# Keep one value per hour
	values_df <- data.frame(downloads=requests$completed)
	groups <- list(group_hour=requests$timestamp)
	requests <- aggregate(values_df, by=groups, FUN=min)
	# Calculate change per hour
	requests$downloads <- append(diff(requests$downloads), NA)
	requests <- requests[complete.cases(requests$downloads),]
	# Return result
	return(requests)
}

calc_size <- function(torrents) {
	torrents$piece_kb <- torrents$piece_size / 1000
	torrents$kilobytes <- torrents$pieces_count * torrents$piece_kb
	torrents$gigabytes <- torrents$kilobytes/1000000
	torrents$piece_kb <- NULL
	torrents$kilobytes <- NULL
	torrents$piece_size <- NULL
	torrents$pieces_count <- NULL
	return(torrents)
}

# Read database
args <- commandArgs(trailingOnly=TRUE)
ret <- read_db(args[1])
peers <- ret[[1]]
torrents <- ret[[2]]
requests <- ret[[3]]

# Prepare data
print("*** Join peers and torrents ***")
print(head(peers))
peers <- merge_with_torrents(peers, torrents)
print(head(peers))
print("*** Filter peers ***")
peers <- filter_peers(peers)
print(head(peers))
stopifnot(nrow(peers) > 0)
print("*** Parse timesamps ***")
peers$last_seen <- hour_timestamps(peers$last_seen)
print(head(peers))
print("*** Aggregated downloads ***")
downloads <- aggregate_time(peers)
print(head(downloads))
print("*** Parse request timestamps ***")
print(head(requests))
requests$timestamp <- hour_timestamps(requests$timestamp)
print(head(requests))
print("*** Calculate torrent size ***")
print(head(torrents))
torrents <- calc_size(torrents)
print(head(torrents))

# Data per torrent
pdf("plots.pdf", width=9, height=6)
for (torrent in unique(downloads$group_torrent)) {
	# Get torrent name
	info <- torrents[torrents$id==torrent,]
	name <- strtrim(info$display_name, 50)
	size <- round(info$gigabytes, digits=1)
	description <- paste("Torrent ", torrent, ": \"", name, "\" (", size, " GB)", sep="")
	print(description)

	# Scrape data
	filtered <- filter_request(requests, torrent)
	if (nrow(filtered) == 0) {
		print("No scrape data")
		scrape <- data.frame(group_hour=NA, downloads=NA)
	} else {
		scrape <- aggregate_complete(filtered)
	}
	print(scrape)

	# Confirmed data
	confirmed <- filter_download(downloads, torrent)
	print(confirmed)

	# Merge on timestamp
	scrape$category <- "scrape"
	confirmed$category <- "confirmed"
	total <- rbind(scrape, confirmed)
	total <- total[complete.cases(total$group_hour),]
	print(total)

	# Plot that shit
	print(
		ggplot(total, aes(factor(total$group_hour), downloads, fill=category)) +
		geom_bar(stat="identity", position="dodge") +
		theme(axis.text.x=element_text(angle=90, hjust=1)) +
		labs(title=description, x="Time UTC", y="Downloads")
	)
}
print("*** End ***")
