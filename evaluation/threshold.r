#!/usr/bin/env Rscript

library(DBI)
library(ggplot2)
library(reshape)

# Read CSV
args <- commandArgs(trailingOnly=TRUE)
threshold <- read.csv(args[1], header=TRUE)

# Prepare data
threshold <- melt(threshold)
threshold$variable <- as.numeric(gsub("X", "", threshold$variable))
print(threshold)

# Create file
outfile = sub(".csv", ".pdf", args[1])
stopifnot(outfile != args[1])
pdf(outfile, width=9, height=2)

# Plot with ggplot2
print(
	ggplot(threshold, aes(x=variable, y=value, color=set)) +
	geom_line() +
	geom_point(size=3) +
	labs(x="Threshold", y="Confirmed Downloads")
)
print(paste("Plot written to", outfile))
print("*** End ***")
