# Install TwoSampleMR and dependencies for Mendelian Randomization analysis

# Set up user library
user_lib <- Sys.getenv("R_LIBS_USER")
if (!dir.exists(user_lib)) {
  dir.create(user_lib, recursive = TRUE)
}
.libPaths(c(user_lib, .libPaths()))

# Install remotes if needed
if (!require("remotes", quietly = TRUE)) {
  install.packages("remotes", repos = "https://cran.r-project.org")
}

# Install TwoSampleMR from GitHub
if (!require("TwoSampleMR", quietly = TRUE)) {
  remotes::install_github("MRCIEU/TwoSampleMR", quiet = TRUE, upgrade = "never")
}

# Install ieugwasr for accessing IEU GWAS database
if (!require("ieugwasr", quietly = TRUE)) {
  remotes::install_github("MRCIEU/ieugwasr", quiet = TRUE, upgrade = "never")
}

# Install additional useful packages
packages <- c("data.table", "ggplot2", "dplyr", "tidyr")
for (pkg in packages) {
  if (!require(pkg, character.only = TRUE, quietly = TRUE)) {
    install.packages(pkg, repos = "https://cran.r-project.org")
  }
}

cat("All packages installed successfully!\n")
cat("TwoSampleMR version:", as.character(packageVersion("TwoSampleMR")), "\n")
