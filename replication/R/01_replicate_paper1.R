# Independent R re-estimation of every regression in paper 1.
#
# Input (replication/data/, written by replication/export_model_frames.py):
#   models.csv            id, script, formula (Python/patsy), cov_type (HC1 or cluster), cluster, nobs
#   frames/{id}.csv       estimation data of each model
#   python_estimates.csv  Python (statsmodels) coefficient and standard error of each term
# Output (replication/output/):
#   paper1_r_estimates.csv   R (fixest) coefficient, standard error and N of each term
#   paper1_r_vs_python.csv   both estimates side by side with absolute differences
#   paper1_r_vs_python.md    summary
#
# Translation of the formulas: C(SG_ID), C(sigun), C(rp), C(ry), C(region) are absorbed as fixed effects;
# C(group == '...') becomes a 0/1 variable; C(group, Treatment('...')) becomes i(group, ref = "...").
# Standard errors: HC1 = vcov "hetero"; clustered = cluster on cluster_id. Both use
# ssc(adj = TRUE, fixef.K = "full", cluster.adj = TRUE), the same small-sample correction as statsmodels
# (fixed-effect dummies counted in K), and keep singleton observations (fixef.rm = "none"), as statsmodels does
# with explicit dummies; coefficients and standard errors should then agree to rounding error.
# r_se_alt reports fixest's own defaults for comparison: singletons removed and the exact number of redundant
# fixed effects (fixef.force_exact = TRUE). It differs only in small samples with many fixed effects.
#
# Run from the repository root:  Rscript replication/R/01_replicate_paper1.R

suppressPackageStartupMessages({
  library(fixest)
  library(data.table)
})

args <- commandArgs(trailingOnly = FALSE)
here <- dirname(normalizePath(sub("^--file=", "", args[grep("^--file=", args)])))
rep_dir <- dirname(here)
dat <- file.path(rep_dir, "data")
out <- file.path(rep_dir, "output")
dir.create(out, showWarnings = FALSE)

models <- fread(file.path(dat, "models.csv"), encoding = "UTF-8")
py <- fread(file.path(dat, "python_estimates.csv"), encoding = "UTF-8")
FE <- c("SG_ID", "sigun", "rp", "ry", "region")

translate <- function(f) {
  rhs_fe <- character(0)
  for (v in FE) {
    pat <- paste0("\\s*\\+\\s*C\\(", v, "\\)")
    if (grepl(pat, f)) {
      rhs_fe <- c(rhs_fe, v)
      f <- gsub(pat, "", f)
    }
  }
  dummy <- regmatches(f, regexpr("C\\(group == '[^']+'\\)", f))
  lev_dummy <- if (length(dummy)) sub("C\\(group == '([^']+)'\\)", "\\1", dummy) else NA
  if (length(dummy)) f <- sub("C\\(group == '[^']+'\\)", "group_is", f, perl = TRUE)
  trt <- regmatches(f, regexpr("C\\(group, Treatment\\('[^']+'\\)\\)", f))
  ref <- if (length(trt)) sub(".*Treatment\\('([^']+)'\\).*", "\\1", trt) else NA
  if (length(trt)) f <- sub("C\\(group, Treatment\\('[^']+'\\)\\)", sprintf('i(group, ref = "%s")', ref), f)
  if (length(rhs_fe)) f <- paste(f, "|", paste(rhs_fe, collapse = " + "))
  list(formula = f, lev_dummy = lev_dummy, ref = ref, has_fe = length(rhs_fe) > 0)
}

# Python term name -> R term name
py_to_r <- function(t, tr) {
  if (t == "Intercept") return("(Intercept)")
  if (grepl("^C\\(group == ", t)) return("group_is")
  if (grepl("^C\\(group, Treatment", t)) return(paste0("group::", sub(".*\\[T\\.(.*)\\]$", "\\1", t)))
  t
}

est <- list()
for (k in seq_len(nrow(models))) {
  m <- models[k]
  d <- fread(file.path(dat, "frames", paste0(m$id, ".csv")), encoding = "UTF-8")
  tr <- translate(m$formula)
  if (!is.na(tr$lev_dummy)) d[, group_is := as.numeric(group == tr$lev_dummy)]
  s <- ssc(adj = TRUE, fixef.K = "full", cluster.adj = TRUE)
  s_alt <- ssc(adj = TRUE, fixef.K = "full", cluster.adj = TRUE, fixef.force_exact = TRUE)
  run <- function(ss, rm) {
    if (m$cov_type == "cluster") {
      feols(as.formula(tr$formula), d, cluster = ~cluster_id, ssc = ss, fixef.rm = rm, warn = FALSE, notes = FALSE)
    } else {
      feols(as.formula(tr$formula), d, vcov = "hetero", ssc = ss, fixef.rm = rm, warn = FALSE, notes = FALSE)
    }
  }
  fit <- run(s, "none")
  alt <- if (tr$has_fe) run(s_alt, "perfect") else fit
  ct <- coeftable(fit)
  sa <- se(alt)
  est[[k]] <- data.table(id = m$id, r_term = rownames(ct), r_coef = ct[, 1], r_se = ct[, 2],
                         r_nobs = nobs(fit), r_se_alt = sa[rownames(ct)], r_nobs_alt = nobs(alt),
                         r_formula = tr$formula)
}
est <- rbindlist(est)
fwrite(est, file.path(out, "paper1_r_estimates.csv"))

py[, r_term := mapply(py_to_r, term, MoreArgs = list(tr = NULL))]
cmp <- merge(py, est, by = c("id", "r_term"), all.x = TRUE)
cmp <- merge(cmp, models[, .(id, script, cov_type)], by = "id")
fe_ids <- models[grepl("C\\((SG_ID|sigun|rp|ry|region)\\)", formula), id]
cmp[, status := fifelse(r_term == "(Intercept)" & id %in% fe_ids, "intercept absorbed by fixed effects",
                fifelse(is.na(se) & is.na(r_coef), "not estimable in either (collinear)",
                fifelse(is.na(r_coef), "dropped in R only",
                fifelse(is.na(se), "Python s.e. undefined",
                fifelse(abs(coef - r_coef) < 1e-6 * pmax(1, abs(coef)) &
                        abs(se - r_se) < 1e-6 * pmax(1, abs(se)) & nobs == r_nobs, "match", "DIFFERENT")))))]
cmp[, `:=`(d_coef = abs(coef - r_coef), d_se = abs(se - r_se))]
setorder(cmp, id, term)
fwrite(cmp[, .(id, script, cov_type, term, coef, r_coef, d_coef, se, r_se, d_se, nobs, r_nobs, status,
               r_se_alt, r_nobs_alt)],
       file.path(out, "paper1_r_vs_python.csv"))

tab <- cmp[, .N, by = status][order(-N)]
cmpd <- cmp[status == "match"]
alt_diff <- cmpd[!is.na(r_se_alt) & abs(r_se_alt / r_se - 1) > 0.01]
lines <- c("# Paper 1: R (fixest) re-estimation compared with the Python (statsmodels) estimates", "",
           sprintf("Models: %d. Terms compared: %d. Generated by `replication/R/01_replicate_paper1.R` (fixest %s, %s).",
                   nrow(models), nrow(cmp), as.character(packageVersion("fixest")), R.version.string), "",
           "| Status | Terms |", "|---|---|", sprintf("| %s | %d |", tab$status, tab$N), "",
           sprintf("Largest absolute difference among matched terms: coefficient %.2e, standard error %.2e.",
                   max(cmpd$d_coef), max(cmpd$d_se)), "",
           "Tolerance: 1e-6 relative to max(1, |value|), and identical N.", "",
           sprintf("Alternative standard errors (fixest defaults: singletons removed, exact count of redundant fixed effects) differ by more than 1 percent for %d terms in %d models; the largest ratio of alternative to reported s.e. is %.3f, the smallest %.3f. The reported (statsmodels) standard errors are the more conservative in every such case: %s.",
                   nrow(alt_diff), uniqueN(alt_diff$id), max(cmpd$r_se_alt / cmpd$r_se, na.rm = TRUE),
                   min(cmpd$r_se_alt / cmpd$r_se, na.rm = TRUE), all(alt_diff$r_se_alt <= alt_diff$r_se)))
bad <- cmp[status %in% c("DIFFERENT", "dropped in R only")]
if (nrow(bad)) {
  lines <- c(lines, "", "## Terms that differ", "", "| Model | Term | Python | R | Python s.e. | R s.e. |",
             "|---|---|---|---|---|---|",
             sprintf("| %s | %s | %.6f | %.6f | %.6f | %.6f |", bad$id, bad$term, bad$coef, bad$r_coef, bad$se, bad$r_se))
}
writeLines(lines, file.path(out, "paper1_r_vs_python.md"), useBytes = TRUE)
cat(lines, sep = "\n")
