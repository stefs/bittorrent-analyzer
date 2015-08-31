#!/usr/bin/env Rscript

library(DBI)
library(ggplot2)
source("util.r")

read_db <- function(path) {
	# Open raw_peersbase connection
	con <- dbConnect(RSQLite::SQLite(), path)
	# Disable auto commit
	dbBegin(con)
	# Read peer table
	sql <- "SELECT id, first_pieces, last_pieces, last_seen, torrent FROM peer"
	peers <- dbGetQuery(con, sql)
	# Read torrent table
	sql <- "SELECT id, pieces_count, gigabyte FROM torrent"
	torrents <- dbGetQuery(con, sql)
	# Read request table
	sql <- "SELECT completed, torrent FROM request ORDER BY timestamp"
	requests <- dbGetQuery(con, sql)
	# Read torrent set csv
	sets <- read.csv(paste(path, ".csv", sep=""))
	# Close database connection
	dbDisconnect(con)
	# Combine tables
	ret <- list(peers, torrents, requests, sets)
	# Return result
	return(ret)
}

merge_with_torrents <- function(peers, torrents) {
	# Inner join
	peers <- merge(peers, torrents, by.x="torrent", by.y="id")
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
	values_df <- data.frame(confirmed=peers$id)
	groups <- list(torrent=peers$torrent, set=peers$set, gigabyte=peers$gigabyte)
	ret <- aggregate(values_df, by=groups, FUN=length)
	# Return result
	return(ret)
}

filter_request <- function(requests) {
	# Delete rows without complete value
	requests <- requests[complete.cases(requests$completed),]
	# Return result
	return(requests)
}

aggregate_scrape <- function(requests) {
	# Calculate all diffs
	scrape <- data.frame(torrent=NA, downloads=NA)
	for (torrent in unique(requests$torrent)) {
		# Filter for current torrent id
		curr_requests <- requests[requests$torrent==torrent,]
		# Check for data for this torrent
		if (nrow(curr_requests) == 0) {
			print("No scrape data")
			next
		}
		# Convert downloads from cumulative to difference
		curr_requests$downloads <- append(NA, diff(sort(curr_requests$completed)))
		curr_requests$completed <- NULL
		# Append to result
		scrape <- rbind(scrape, curr_requests)
	}
	# Discard rows without download value
	scrape <- scrape[complete.cases(scrape$downloads),]
	# Sum everything per torrent
	values_df <- data.frame(scrape=scrape$downloads)
	groups <- list(torrent=scrape$torrent)
	scrape <- aggregate(values_df, by=groups, FUN=sum)
	# Return result
	return(scrape)
}

# Read database
args <- commandArgs(trailingOnly=TRUE)
ret <- read_db(args[1])
peers <- ret[[1]]
torrents <- ret[[2]]
requests <- ret[[3]]
sets <- ret[[4]]

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
print("*** Merge with torrent sets ***")
peers <- merge(peers, sets, by="torrent")
print(head(peers))
print(head(requests))
print("*** Aggregate downloads ***")
confirmed <- aggregate_confirmed(peers)
requests <- filter_request(requests)
scrape <- aggregate_scrape(requests)
print(head(requests))
print(head(scrape))
print("*** Merge confirmed and scrape ***")
total <- merge(scrape, confirmed, by="torrent")
total$confirmed_per_scrape <- total$confirmed / total$scrape
print(total)

# Create file
outfile = sub(".sqlite", "_download_confirmed_scrape.pdf", args[1])
stopifnot(outfile != args[1])
pdf(outfile, width=9, height=2.5)

# Plot with ggplot2
gb_breaks <- c(1, 3.2, 10, 32, 100)
y_breaks <- round(10^((-2:7)*0.25)/10, digits=2)
print(
	ggplot(total, aes(x=gigabyte, y=confirmed_per_scrape)) +
	geom_segment(x=min(gb_breaks),xend=max(gb_breaks),y=1,yend=1, show_guide=FALSE, color="black") +
	geom_point(aes(fill=set), size=4, colour="black", pch=21) +
	scale_x_continuous(breaks=gb_breaks, labels=gb_breaks) +
	scale_y_continuous(breaks=y_breaks) +
	coord_trans(x="log10", limx=c(min(gb_breaks), max(gb_breaks)), y="log10", limy=c(min(y_breaks), max(y_breaks)))
)
x_breaks <- round(10^((5:11)*0.5)/10, digits=0)
y_breaks <- round(10^((9:17)*0.25)/10, digits=0)
print(
	ggplot(total, aes(x=scrape, y=confirmed)) +
	geom_point(aes(size=gigabyte, fill=set), colour="black", pch=21) +
	scale_size(range=c(2.5,8), breaks=gb_breaks, labels=gb_breaks, trans="log10") +
	geom_abline(intercept=0, slope=1) +
	scale_x_continuous(breaks=x_breaks, labels=x_breaks) +
	scale_y_continuous(breaks=y_breaks) +
	coord_trans(x="log10", limx=c(min(x_breaks), max(x_breaks)), y="log10", limy=c(min(y_breaks), max(y_breaks)))
)
print(paste("Plot written to", outfile))
print("*** End ***")
