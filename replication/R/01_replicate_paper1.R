# Independent R re-estimation of every regression in paper 1.
#
# Input (replication/data/paper1/, written by replication/export_model_frames.py paper1):
#   models.csv            id, script, formula (Python/patsy), cov_type (HC1 or cluster), cluster, nobs
#   frames/{id}.csv       estimation data of each model
#   python_estimates.csv  Python (statsmodels) coefficient and standard error of each term
# Output (replication/output/):
#   paper1_r_estimates.csv   R (fixest) coefficient, standard error and N of each term
#   paper1_r_vs_python.csv   both estimates side by side with absolute differences
#   paper1_r_vs_python.md    summary
# Fixed effects: C(SG_ID), C(sigun), C(rp), C(ry), C(region). Translation and standard errors: see replicate_lib.R.
#
# Run from the repository root:  Rscript replication/R/01_replicate_paper1.R

args <- commandArgs(trailingOnly = FALSE)
source(file.path(dirname(normalizePath(sub("^--file=", "", args[grep("^--file=", args)]))), "replicate_lib.R"))

FE <- c("SG_ID", "sigun", "rp", "ry", "region")
p <- rep_dirs("paper1")
r <- estimate_all(p$dat, FE)
cmp <- compare(p$dat, r$models, r$est, FE)
write_outputs("paper1", p$out, r$est, cmp)
lines <- summary_lines("Paper 1: R (fixest) re-estimation compared with the Python (statsmodels) estimates",
                       "01_replicate_paper1.R", r$models, cmp)
writeLines(lines, file.path(p$out, "paper1_r_vs_python.md"), useBytes = TRUE)
cat(lines, sep = "\n")
