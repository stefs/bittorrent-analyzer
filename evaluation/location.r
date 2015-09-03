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
	sql <- "SELECT country FROM peer"
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

country_count <- function(peer) {
	# Aggregate speed per country
	values_df <- data.frame(count=peer$country)
	groups <- list(country=peer$country)
	ret <- aggregate(values_df, by=groups, FUN=length)
	# Return result
	return(ret)
}

# Read database
args <- commandArgs(trailingOnly=TRUE)
ret <- read_db(args[1])
peer <- ret[[1]]
torrent <- ret[[2]]

# Prepare data
print("*** Count countries ***")
country <- country_count(peer)
print(head(country))

# File for rworldmap
outfile = sub(".sqlite", "_location_map.pdf", args[1])
stopifnot(outfile != args[1])
mapDevice("pdf", file=outfile)

# Plot with rworldmap
f_breaks = round(10^((3:12)*0.5)/10, digits=-1)
print(f_breaks)
spdf <- joinCountryData2Map(country, joinCode="ISO2", nameJoinColumn="country")
mapParams <- mapCountryData(
	spdf,
	nameColumnToPlot="count",
	mapTitle="",
	colourPalette=c("#800000", "#84fbff", "#118000"),
	catMethod=f_breaks#"logfixedWidth"#m_breaks
)
do.call(addMapLegend, c(mapParams, legendLabels="all"))
print(paste("Plot written to", outfile))
print("*** End ***")
