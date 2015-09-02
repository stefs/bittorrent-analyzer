#!/usr/bin/env Rscript

library(DBI)
library(ggplot2)
library(reshape)
library(rworldmap)

read_db <- function(path) {
	# Open raw_peersbase connection
	con <- dbConnect(RSQLite::SQLite(), path)
	# Disable auto commit
	dbBegin(con)
	# Read peer table
	sql <- "SELECT country, max_speed, torrent FROM peer"
	statistic <- dbGetQuery(con, sql)
	# Read torrent table
	sql <- "SELECT id, piece_size FROM torrent"
	torrent <- dbGetQuery(con, sql)
	# Close database connection
	dbDisconnect(con)
	# Combine tables
	ret <- list(statistic, torrent)
	# Return result
	return(ret)
}

merge_with_torrents <- function(peer, torrent) {
	# Inner join
	peer <- merge(peer, torrent, by.x="torrent", by.y="id")
	# Drop torrent info
	peer$torrent <- NULL
	# Return result
	return(peer)
}

filter_peers <- function(peer) {
	# Drop NA speeds
	peer <- peer[complete.cases(peer$max_speed),]
	# Drop impossible speeds
	peer <- peer[peer$max_speed>0,]
	# Return result
	return(peer)
}

calc_kbyteps <- function(peer) {
	# Calculate kilobytes per second
	peer$kbyteps <- (peer$max_speed * peer$piece_size) / 1000
	# Drop source values
	peer$max_speed <- NULL
	peer$piece_size <- NULL
	# Return result
	return(peer)
}

top_samples <- function(peer, top) {
	# Count country frequency
	values_df <- data.frame(count=peer$kbyteps)
	groups <- list(country=peer$country)
	country_count <- aggregate(values_df, by=groups, FUN=length)
	# Keep only top x
    country_count <- country_count[order(-country_count$count),]
    country_count <- head(country_count, n=top)
	# Merge with peer
	peer <- merge(peer, country_count, by="country", all=FALSE)
	# Return result
	return(peer)
}

country_summary <- function(peer) {
	# Aggregate speed per country
	values_df <- data.frame(kbyteps=peer$kbyteps)
	groups <- list(country=peer$country, n=peer$count)
	ret <- aggregate(values_df, by=groups, FUN=summary)
	# Delete count
	peer$count <- NULL
	# Return result
	return(ret)
}

country_mean <- function(peer) {
	# Aggregate speed per country
	values_df <- data.frame(kbyteps=peer$kbyteps)
	groups <- list(country=peer$country)
	ret <- aggregate(values_df, by=groups, FUN=median)
	# Return result
	return(ret)
}

# Read database
args <- commandArgs(trailingOnly=TRUE)
ret <- read_db(args[1])
peer <- ret[[1]]
torrent <- ret[[2]]

# Prepare data
print("*** Merge peer and torrent ***")
peer <- merge_with_torrents(peer, torrent)
print(head(peer))
print("*** Filter for positive speed ***")
peer <- filter_peers(peer)
print(head(peer))
print("*** KBytes per second ***")
peer <- calc_kbyteps(peer)
print(head(peer))
print("*** Sample size top x ***")
peer <- top_samples(peer, 100) # 70 for boxplot, 100 for map
print(head(peer))
print("*** Country mean ***")
country <- country_mean(peer)
print(country)
print("*** Print country summary ***")
print(country_summary(peer))

# File for rworldmap
outfile = sub(".sqlite", "_speed_map.pdf", args[1])
stopifnot(outfile != args[1])
mapDevice("pdf", file=outfile)

# Plot with rworldmap
m_breaks <- round(10^((6:16)*(1/3))/10, digits=0)
print(m_breaks)
spdf <- joinCountryData2Map(country, joinCode="ISO2", nameJoinColumn="country")
mapParams <- mapCountryData(
	spdf,
	nameColumnToPlot="kbyteps",
	mapTitle=NA,
	colourPalette=c("#800000", "#84fbff", "#118000"),
	catMethod=m_breaks
)
do.call(addMapLegend, c(mapParams, legendLabels="all"))
print(paste("Plot written to", outfile))

# Create file for ggplot
outfile = sub(".sqlite", "_speed_plot.pdf", args[1])
stopifnot(outfile != args[1])
pdf(outfile, width=10, height=3)

# Plot with ggplot2
y_breaks = round(10^((-3:8)*1.0)/10, digits=6)
f_breaks = round(10^((0:23)*0.25)/10, digits=-1)
print(
	ggplot(data=peer, aes(x=factor(country), y=kbyteps)) +
	scale_y_log10(breaks=y_breaks) +
	geom_boxplot(aes(fill=count), outlier.size=1) +
	scale_fill_continuous(trans="log10", breaks=f_breaks, low="#55b1f7", high="#f75555", name="peers") +
	theme(axis.text.x=element_text(angle=90, hjust=1)) +
	labs(x="Country", y="Kilobytes per Second")
)
print(paste("Plot written to", outfile))
print("*** End ***")
