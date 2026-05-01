# v0.1 TODO

## Real download URLs + fetch implementation

### Registry (`pm_bench/registry.yml`)
- [ ] bpi2012: resolve 4TU direct download URL and pin sha256
- [ ] bpi2017: resolve 4TU direct download URL and pin sha256
- [ ] bpi2018: resolve 4TU direct download URL and pin sha256
- [ ] bpi2019: resolve 4TU direct download URL and pin sha256
- [ ] bpi2020: decide which sub-files to include; resolve individual URLs and pin sha256 per file
- [ ] sepsis: resolve 4TU direct download URL and pin sha256
- [ ] helpdesk: resolve Mendeley direct CSV download URL and pin sha256

### Fetch implementation (`pm_bench/fetch.py`)
- [ ] Implement HTTP download with resume support (Range header)
- [ ] Implement sha256 verification after download
- [ ] Implement atomic move from `.tmp` to final path
- [ ] Wire `_cache.cache_dir()` as the default cache root
- [ ] Handle the bundled `synthetic-toy` case (return path without HTTP)

### Cache (`pm_bench/_cache.py`)
- [ ] Verify `cache_dir()` creates the directory if it doesn't exist
- [ ] Verify `PM_BENCH_CACHE` env var override works end-to-end

### Tests (`tests/test_fetch.py`)
- [ ] Fill in all TODO tests once `fetch_dataset` is implemented
