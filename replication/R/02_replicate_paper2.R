# Independent R re-estimation of every regression in paper 2, and of its two permutation tests.
#
# Input (replication/data/paper2/, written by replication/export_model_frames.py paper2):
#   models.csv            id, script, formula (Python/patsy), cov_type (cluster or nonrobust), cluster, weights, nobs
#   frames/{id}.csv       estimation data of each model
#   python_estimates.csv  Python (statsmodels) coefficient and standard error of each term
#   perm/{script}_controls.csv, perm/{script}_draws.csv, perm/python_perm.csv
#                         control units' panel, the 1,000 placebo assignments and the reported permutation p
# Output (replication/output/):
#   paper2_r_estimates.csv   R (fixest) coefficient, standard error and N of each term
#   paper2_r_vs_python.csv   both estimates side by side with absolute differences
#   paper2_r_perm.csv        permutation p in R and in Python
#   paper2_r_vs_python.md    summary
# Fixed effects: C(SG_ID), C(rp), C(ry), C(block), C(oa), C(year). Translation and standard errors: replicate_lib.R.
#
# Permutation tests (zone_event_study, emp_supply): the pooled coefficient on post (treated and year >= onset) is
# compared with 1,000 placebo coefficients, each from the control units alone with the real onset years given to
# randomly drawn controls, on the same 시군 + region x year fixed effects. The draws are the ones made in Python, so
# p should agree exactly. p = share of placebo |b| >= actual |b|.
#
# Run from the repository root:  Rscript replication/R/02_replicate_paper2.R

args <- commandArgs(trailingOnly = FALSE)
source(file.path(dirname(normalizePath(sub("^--file=", "", args[grep("^--file=", args)]))), "replicate_lib.R"))

FE <- c("SG_ID", "rp", "ry", "block", "oa", "year")
p <- rep_dirs("paper2")
r <- estimate_all(p$dat, FE)
cmp <- compare(p$dat, r$models, r$est, FE)
write_outputs("paper2", p$out, r$est, cmp)

# permutation tests
pp <- fread(file.path(p$dat, "perm", "python_perm.csv"), encoding = "UTF-8")
prow <- list()
for (s in unique(pp$script)) {
  ctrl <- fread(file.path(p$dat, "perm", paste0(s, "_controls.csv")), encoding = "UTF-8")
  dr <- fread(file.path(p$dat, "perm", paste0(s, "_draws.csv")), encoding = "UTF-8")
  nd <- max(dr$draw)
  P <- matrix(0, nrow(ctrl), nd)
  for (i in seq_len(nd)) {
    o <- dr[draw == i]
    on <- o$onset[match(ctrl$SG_ID, o$SG_ID)]
    P[, i] <- as.numeric(!is.na(on) & ctrl$year >= on)
  }
  ys <- pp[script == s, y]
  dm <- demean(cbind(as.matrix(ctrl[, ..ys]), P), f = ctrl[, .(SG_ID, ry)], tol = 1e-13, iter = 100000)
  Pd <- dm[, -seq_along(ys), drop = FALSE]
  for (yv in ys) {
    f_y <- paste0(yv, " ~ post + C(SG_ID) + C(ry)")
    mid <- r$models[script == s & cov_type == "cluster" & formula == f_y, id]
    b <- r$est[id == mid & r_term == "post", r_coef]
    pb <- colSums(Pd * dm[, yv]) / colSums(Pd^2)
    prow[[length(prow) + 1]] <- data.table(script = s, y = yv, model = mid, r_coef = b,
                                           py_coef = pp[script == s & y == yv, coef],
                                           r_p_perm = mean(abs(pb) >= abs(b)),
                                           py_p_perm = pp[script == s & y == yv, p_perm],
                                           placebo_lo = quantile(pb, 0.025, names = FALSE),
                                           placebo_hi = quantile(pb, 0.975, names = FALSE), draws = nd)
  }
}
perm <- rbindlist(prow)
# the scripts print the coefficient to two (zone_event_study) or three (emp_supply) decimals and p to three
perm[, match := abs(r_p_perm - py_p_perm) < 5e-4 & abs(r_coef - py_coef) < 5e-3]
fwrite(perm, file.path(p$out, "paper2_r_perm.csv"))

lines <- summary_lines("Paper 2: R (fixest) re-estimation compared with the Python (statsmodels) estimates",
                       "02_replicate_paper2.R", r$models, cmp)
lines <- c(lines, "", "## Permutation tests", "",
           sprintf("%d outcomes in %d tests, %d placebo draws each (the draws made in Python). Permutation p agrees for %d of %d outcomes.",
                   nrow(perm), uniqueN(perm$script), perm$draws[1], sum(perm$match), nrow(perm)), "",
           "| Test | Outcome | Coefficient (R) | p (R) | p (Python) |", "|---|---|---|---|---|",
           sprintf("| %s | %s | %.3f | %.3f | %.3f |", perm$script, perm$y, perm$r_coef, perm$r_p_perm, perm$py_p_perm))
writeLines(lines, file.path(p$out, "paper2_r_vs_python.md"), useBytes = TRUE)
cat(lines, sep = "\n")
