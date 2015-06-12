#!/usr/bin/env Rscript

library(DBI)

read_db <- function(path){
	# Open raw_peersbase connection
	con <- dbConnect(RSQLite::SQLite(), path)
	# Disable auto commit
	dbBegin(con)

	# DEBUG: imports only year of last_seen, first_seen is fine
	sql <- "SELECT first_seen, last_seen FROM peer LIMIT 100"
	peers <- dbGetQuery(con, sql)
	print(peers)
	print(typeof(peers$first_seen))
	print(typeof(peers$last_seen))
	stop("breakpoint")

	# Read peer table
	sql <- "SELECT id, first_pieces, last_pieces, last_seen, torrent FROM peer"
	peers <- dbGetQuery(con, sql)
	# Read torrent table
	sql <- "SELECT id, complete_threshold FROM torrent"
	torrents <- dbGetQuery(con, sql)
	# Close database connection
	dbDisconnect(con)
	# Combine tables
	ret <- list(peers, torrents)
	# Return result
	return(ret)
}

merge_with_torrents <- function(peers, torrents){
	# Inner join
	peers <- merge(peers, torrents, by.x="torrent", by.y="id")
	# Return result
	return(peers)
}

filter_peers <- function(peers){
	# Filter for usable last pieces
	peers <- peers[complete.cases(peers$last_pieces),]
	# Filter according to threshold
	peers <- peers[peers$first_pieces < peers$complete_threshold,]
	peers <- peers[peers$last_pieces >= peers$complete_threshold,]
	# Return result
	return(peers)
}

hour_timestamps <- function(timestamps){
	# Parse timestamps
	timestamps <- as.POSIXct(timestamps, tz="GMT")
	# Truncate to hours
	timestamps <- trunc(timestamps, units="hours")
	# Revert to strings
	timestamps <- as.character(timestamps)
	# Return result
	return(timestamps)
}

aggregate_time <- function(peers){
	# Aggregate by torrent id and last seen
	values_df <- data.frame(peer_count=peers$id)
	groups <- list(group_torrent=peers$torrent, group_last_seen=peers$last_seen)
	ret <- aggregate(values_df, by=groups, FUN=length)
	# Return result
	return(ret)
}

plot_downloads <- function(downloads){
	# For each torrent id
	for (torrent in unique(downloads$group_torrent)) {
		# Extract all rows with that id
		values <- downloads[downloads$group_torrent==torrent,]
		# Create barplot
		values <- downloads$peer_count
		names(values) <- downloads$group_last_seen
		barplot(values)
	}
}

args <- commandArgs(trailingOnly=TRUE)
print("*** Read from database ***")
ret <- read_db(args[1])
peers <- ret[[1]]
torrents <- ret[[2]]
print(head(peers))
print(torrents)
print("*** Join peers and torrents ***")
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
print(downloads)
print("*** Plot downloads ***")
plot_downloads(downloads)
print("*** End ***")

