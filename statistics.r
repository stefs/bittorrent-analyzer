#!/usr/bin/env Rscript

library(DBI)

read_db <- function(path){
	# Open raw_peersbase connection
	con <- dbConnect(RSQLite::SQLite(), path)
	# Disable auto commit
	dbBegin(con)
	# Read peer table
	sql <- "SELECT id, first_pieces, last_pieces, last_seen, torrent FROM peer"
	peers <- dbGetQuery(con, sql)
	# Read torrent table
	sql <- "SELECT id, complete_threshold, info_hash_hex, display_name FROM torrent"
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
	peers <- peers[peers$first_pieces < peers$complete_threashold & peers$last_pieces >= peers$complete_threshold,]
	# Parse timestamps and truncate to hours
	peers$last_seen <- as.POSIXct(peers$last_seen, tz="GMT")
	peers$last_seen <- trunc(peers$last_seen, units="hours")
	peers$last_seen <- as.character(peers$last_seen)
	# Return result
	return(peers)
}

aggregate_time <- function(peers){
	# Aggregate by last seen and torrent
	values_df <- data.frame(pieces_delta=peers$pieces_delta)
	groups <- list(last_seen=peers$last_seen, torrent=peers$torrent)
	aggregated_peers <- aggregate(values_df, by=groups, FUN=sum)
	# Return result
	return(aggregated_peers)
}

plot_downloads_t1 <- function(peers){
	# Filter for first torrent
	peers <- peers[peers$torrent==1,]
	# Create barplot
	values <- peers$pieces_delta
	names(values) <- peers$last_seen
	barplot(values)
}

args <- commandArgs(trailingOnly=TRUE)
print("*** Read for database ***")
peers, torrents <- read_db(args[1])
print(head(peers))
print(head(torrents))
print("*** Join peers and torrents ***")
peers <- merge_with_torrents(peers, torrents)
print(head(peers))
print("*** Filter peers ***")
peers <- filter_peers(peers)
print(head(peers))
print("*** Aggregated downloads ***")
peers <- aggregate_time(peers)
print(peers)
print("*** Plot downloads ***")
plot_downloads_t1(peers)
print("*** End ***")

