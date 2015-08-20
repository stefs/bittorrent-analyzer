#!/usr/bin/env Rscript

library(DBI)
library(ggplot2)
source("util.r")

read_db <- function(path, torrent_set) {
	# Open raw_peersbase connection
	con <- dbConnect(RSQLite::SQLite(), path)
	# Disable auto commit
	dbBegin(con)
	# Read peer table
	sql <- paste("SELECT id, first_pieces, last_pieces, last_seen, torrent FROM peer WHERE peer.torrent IN", torrent_set)
	peers <- dbGetQuery(con, sql)
	# Read torrent table
	sql <- "SELECT id, pieces_count FROM torrent"
	torrents <- dbGetQuery(con, sql)
	# Read request table
	sql <- paste("SELECT timestamp, completed, torrent FROM request WHERE request.torrent IN", torrent_set)
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
	# Delete torrent
	peers$torrent <- NULL
	# Return result
	return(peers)
}

evaluation_threshold <- function(peers, threshold) {
	# Calculate threshold in pieces
	peers$threshold = ceiling(peers$pieces_count * threshold)
	# Drop pieces count
	peers$pieces_count <- NULL
	# Return result
	return(peers)
}

filter_peers <- function(peers) {
	# Filter for usable last pieces
	peers <- peers[complete.cases(peers$last_pieces),]
	# Filter according to threshold
	peers <- peers[peers$first_pieces < peers$threshold,]
	peers <- peers[peers$last_pieces >= peers$threshold,]
	# Drop unnecessary values
	peers$first_pieces <- NULL
	peers$last_pieces <- NULL
	peers$threshold <- NULL
	# Return result
	return(peers)
}

aggregate_confirmed <- function(peers) {
	# Aggregate by torrent id and last seen
	values_df <- data.frame(downloads=peers$id)
	groups <- list(group_hour=peers$last_seen)
	ret <- aggregate(values_df, by=groups, FUN=length)
	# Return result
	return(ret)
}

filter_request <- function(requests) {
	# Delete rows without complete value
	requests <- requests[complete.cases(requests$completed),]
	# Keep one value per hour and torrent
	values_df <- data.frame(completed=requests$completed)
	groups <- list(group_hour=requests$timestamp, group_torrent=requests$torrent)
	requests <- aggregate(values_df, by=groups, FUN=min)
	# Return result
	return(requests)
}

aggregate_scrape <- function(requests) {
	# Calculate change per hour per torrent
	scrape <- data.frame(group_hour=NA, downloads=NA)
	for (torrent in unique(requests$group_torrent)) {
		# Filter for current torrent id
		curr_requests <- requests[requests$group_torrent==torrent,]
		curr_requests$group_torrent <- NULL
		# Check for data for this torrent
		if (nrow(curr_requests) == 0) {
			print("No scrape data")
			next
		}
		# Convert downloads from cumulative to difference
		curr_requests$downloads <- append(diff(curr_requests$completed), NA)
		curr_requests$completed <- NULL
		# Append to result
		scrape <- rbind(scrape, curr_requests)
	}
	# Discard rows without download value
	scrape <- scrape[complete.cases(scrape$downloads),]
	# Aggregate by hour, sum torrents
	values_df <- data.frame(downloads=scrape$downloads)
	groups <- list(group_hour=scrape$group_hour)
	scrape <- aggregate(values_df, by=groups, FUN=sum)
	# Return result
	return(scrape)
}

# Read database
args <- commandArgs(trailingOnly=TRUE)
torrent_set <- args[1]
ret <- read_db(args[2], torrent_set)
peers <- ret[[1]]
torrents <- ret[[2]]
requests <- ret[[3]]

# Prepare data
print(head(peers))
print("*** Join peers and torrents ***")
peers <- merge_with_torrents(peers, torrents)
print(head(peers))
print("*** Calculate evaluation threshold ***")
peers <- evaluation_threshold(peers, 0.98)
print(head(peers))
print("*** Filter peers ***")
peers <- filter_peers(peers)
print(head(peers))
stopifnot(nrow(peers) > 0)
print("*** Parse timesamps ***")
peers$last_seen <- hour_timestamps(peers$last_seen)
print(head(peers))
requests$timestamp <- hour_timestamps(requests$timestamp)
print(head(requests))
print("*** Aggregate downloads ***")
confirmed <- aggregate_confirmed(peers)
requests <- filter_request(requests)
scrape <- aggregate_scrape(requests)
print(head(scrape))
print("*** Merge confirmed and scrape ***")
scrape$category <- "scrape"
confirmed$category <- "confirmed"
total <- rbind(scrape, confirmed)
total <- total[complete.cases(total$group_hour),]
print(head(total))

# Create file
filename = paste("_download_set_", torrent_set, ".pdf", sep="")
outfile = sub(".sqlite", filename, args[2])
stopifnot(outfile != args[2])
pdf(outfile, width=9, height=4.2)

# Make description
description <- paste("Torrent Set:", torrent_set)
print(description)

# Plot with ggplot2
print(
	ggplot(total, aes(factor(total$group_hour), downloads, fill=category)) +
	geom_bar(stat="identity", position="dodge") +
	theme(axis.text.x=element_text(angle=90, hjust=1)) +
	labs(title=description, x="Time UTC (day/hour)", y="Downloads")
)
print(paste("Plot written to", outfile))
print("*** End ***")
