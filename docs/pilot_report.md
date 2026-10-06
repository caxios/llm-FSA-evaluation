# Pilot Report (P7) — agent T, prompt v1.2

## Gates

| gate | metric | value | threshold | result | note |
|---|---|---|---|---|---|
| G1 Schema | valid / all runs | 1.000 | >= 95% | PASS | 3420/3420 runs |
| G2 Calculation | share of valid T runs with eps > 5% | 0.000 | < 30% | PASS | median eps 0.000% |
| G3 Signal | large caps mean(beta_A - beta_C) | 0.181 | 90% CI excludes 0 or |mean| >= 0.10 | PASS | 90% CI [-0.129, 0.573], 10 firms |
| G4 Measurability | firms with a feasible cash size at n <= 20 | 0.000 | >= 80% | FAIL | 0/20 firms |
| G5 Data | ITM small caps with CB truth; E8 validity | 1.000 | >= 30 firms; >= 90% valid | PASS | 50 ITM firms; E8 valid 390/390 |

## Diagnostics

- nonpositive_baseline_firms: 4
- nonpositive_run_share: 0.208
- refusal_or_invalid_share: 0.000
- mean_latency_s: 3.530
- unit_slip_share: 0.015
- korean_rationale_share: 1.000

### Elasticities

| firm_id | condition | beta | se_hc3 | n_used | n_nonpositive_dropped |
|---|---|---|---|---|---|
| L001 | A | 0.790 | 0.102 | 50.000 | 0.000 |
| L001 | C | 0.937 | 0.074 | 69.000 | 1.000 |
| L006 | A | 1.236 | 0.191 | 50.000 | 0.000 |
| L006 | C | 0.497 | 0.198 | 69.000 | 1.000 |
| L011 | A | 0.890 | 0.036 | 50.000 | 0.000 |
| L011 | C | 0.969 | 0.027 | 70.000 | 0.000 |
| L016 | A | 0.967 | 0.039 | 50.000 | 0.000 |
| L016 | C | 0.961 | 0.024 | 70.000 | 0.000 |
| L021 | A | 0.909 | 0.030 | 50.000 | 0.000 |
| L021 | C | 1.089 | 0.051 | 70.000 | 0.000 |
| L026 | A | 0.190 | 0.274 | 41.000 | 9.000 |
| L026 | C | 0.551 | 0.527 | 56.000 | 14.000 |
| L031 | A | 2.038 | 0.577 | 27.000 | 23.000 |
| L031 | C | -0.120 | 0.329 | 29.000 | 41.000 |
| L036 | A | 0.890 | 0.133 | 49.000 | 1.000 |
| L036 | C | 1.038 | 0.120 | 70.000 | 0.000 |
| L041 | A | 0.929 | 0.069 | 49.000 | 1.000 |
| L041 | C | 1.012 | 0.144 | 69.000 | 1.000 |
| L046 | A | 1.110 | 0.058 | 50.000 | 0.000 |
| L046 | C | 1.200 | 0.123 | 70.000 | 0.000 |
| S001 | A | 0.823 | 0.436 | 9.000 | 41.000 |
| S001 | C | 1.515 | 0.525 | 25.000 | 45.000 |
| S006 | A | 0.688 | 0.415 | 36.000 | 14.000 |
| S006 | C | 0.845 | 0.909 | 23.000 | 47.000 |
| S011 | A | 1.963 | 0.626 | 50.000 | 0.000 |
| S011 | C | -0.037 | 0.339 | 70.000 | 0.000 |
| S016 | A | 0.751 | 0.491 | 38.000 | 12.000 |
| S016 | C | 1.033 | 0.450 | 58.000 | 12.000 |
| S021 | A | 0.833 | 0.328 | 49.000 | 1.000 |
| S021 | C | 0.808 | 0.401 | 66.000 | 4.000 |
| S026 | A | 0.681 | 0.833 | 25.000 | 25.000 |
| S026 | C | 1.389 | 1.463 | 17.000 | 53.000 |
| S031 | A | – | – | 0.000 | 50.000 |
| S031 | C | – | – | 0.000 | 70.000 |
| S036 | A | 2.108 | 0.865 | 47.000 | 3.000 |
| S036 | C | 2.560 | 0.731 | 64.000 | 6.000 |
| S041 | A | 3.893 | 0.662 | 45.000 | 5.000 |
| S041 | C | 3.705 | 0.538 | 61.000 | 9.000 |
| S046 | A | 2.709 | 0.549 | 50.000 | 0.000 |
| S046 | C | 1.592 | 0.360 | 69.000 | 1.000 |

### Baseline (E0 / k = 1)

| firm_id | condition | v0 | sigma | n_valid | n_total | shares_agent |
|---|---|---|---|---|---|---|
| L001 | A | 165,320 | 35,591 | 10.000 | 10.000 | 5,827,808,935 |
| L001 | C | 163,546 | 53,267 | 30.000 | 30.000 | 5,827,808,935 |
| L006 | A | 1,122,703 | 557,482 | 10.000 | 10.000 | 51,448,788 |
| L006 | C | 1,467,744 | 556,999 | 30.000 | 30.000 | 51,448,788 |
| L011 | A | 593,853 | 28,691 | 10.000 | 10.000 | 162,167,581 |
| L011 | C | 585,293 | 61,660 | 30.000 | 30.000 | 169,976,544 |
| L016 | A | 371,533 | 19,575 | 10.000 | 10.000 | 149,579,777 |
| L016 | C | 360,492 | 27,191 | 30.000 | 30.000 | 149,579,777 |
| L021 | A | 32,742 | 5,688 | 10.000 | 10.000 | 95,312,200 |
| L021 | C | 27,048 | 1,938 | 30.000 | 30.000 | 95,312,200 |
| L026 | A | 249,996 | 883,919 | 10.000 | 10.000 | 70,592,343 |
| L026 | C | 292,775 | 251,582 | 30.000 | 30.000 | 70,592,343 |
| L031 | A | 28,565 | 36,832 | 10.000 | 10.000 | 88,946,220 |
| L031 | C | -861 | 37,988 | 30.000 | 30.000 | 88,946,220 |
| L036 | A | 154,968 | 67,110 | 10.000 | 10.000 | 111,355,765 |
| L036 | C | 145,152 | 59,235 | 30.000 | 30.000 | 111,355,765 |
| L041 | A | 88,195 | 7,448 | 10.000 | 10.000 | 170,444,487 |
| L041 | C | 84,502 | 14,800 | 30.000 | 30.000 | 175,922,788 |
| L046 | A | 156,684 | 17,411 | 10.000 | 10.000 | 77,377,800 |
| L046 | C | 145,909 | 15,367 | 30.000 | 30.000 | 77,377,800 |
| S001 | A | -5,317 | 2,979 | 10.000 | 10.000 | 13,335,216 |
| S001 | C | 1,615 | 3,205 | 30.000 | 30.000 | 13,335,216 |
| S006 | A | 198 | 443 | 10.000 | 10.000 | 37,673,903 |
| S006 | C | -264 | 495 | 30.000 | 30.000 | 37,673,903 |
| S011 | A | 1,882 | 986 | 10.000 | 10.000 | 23,307,078 |
| S011 | C | 1,712 | 2,546 | 30.000 | 30.000 | 23,307,078 |
| S016 | A | 2,310 | 1,740 | 10.000 | 10.000 | 20,601,646 |
| S016 | C | 2,902 | 2,171 | 30.000 | 30.000 | 20,601,646 |
| S021 | A | 6,937 | 2,189 | 10.000 | 10.000 | 33,543,004 |
| S021 | C | 4,926 | 1,429 | 30.000 | 30.000 | 32,875,765 |
| S026 | A | 556 | 532 | 10.000 | 10.000 | 34,648,787 |
| S026 | C | -201 | 2,143 | 30.000 | 30.000 | 34,648,787 |
| S031 | A | -19,719 | 3,151 | 10.000 | 10.000 | 11,690,462 |
| S031 | C | -21,384 | 2,570 | 30.000 | 30.000 | 11,690,462 |
| S036 | A | 9,481 | 4,618 | 10.000 | 10.000 | 10,630,784 |
| S036 | C | 11,396 | 21,179 | 30.000 | 30.000 | 10,630,784 |
| S041 | A | 677 | 977 | 10.000 | 10.000 | 42,620,470 |
| S041 | C | 274 | 463 | 30.000 | 30.000 | 42,620,470 |
| S046 | A | 2,194 | 1,166 | 10.000 | 10.000 | 65,374,456 |
| S046 | C | 1,550 | 769 | 30.000 | 30.000 | 65,374,456 |

### Sigma stability (sigma from first n reps / sigma from all)

| firm_id | n_valid | sigma_all | cv_all | rel_5 | rel_10 | rel_15 | rel_20 |
|---|---|---|---|---|---|---|---|
| L001 | 20 | 53,875 | 0.329 | 0.861 | 1.015 | 1.002 | 1.000 |
| L006 | 20 | 541,693 | 0.376 | 0.932 | 1.131 | 1.096 | 1.000 |
| L011 | 20 | 63,336 | 0.108 | 0.410 | 0.922 | 1.155 | 1.000 |
| L016 | 20 | 26,217 | 0.073 | 0.531 | 1.163 | 1.106 | 1.000 |
| L021 | 20 | 2,021 | 0.075 | 1.185 | 0.825 | 0.843 | 1.000 |
| L026 | 20 | 287,109 | 1.066 | 0.807 | 0.552 | 1.074 | 1.000 |
| L031 | 20 | 36,147 | 5.801 | 1.555 | 1.203 | 1.112 | 1.000 |
| L036 | 20 | 52,346 | 0.361 | 0.218 | 1.414 | 1.156 | 1.000 |
| L041 | 20 | 17,046 | 0.202 | 0.678 | 0.563 | 0.700 | 1.000 |
| L046 | 20 | 15,267 | 0.102 | 1.381 | 1.056 | 1.092 | 1.000 |
| S001 | 20 | 3,357 | 9.880 | 0.916 | 0.884 | 0.931 | 1.000 |
| S006 | 20 | 504 | 1.853 | 1.293 | 0.983 | 0.982 | 1.000 |
| S011 | 20 | 2,726 | 1.461 | 1.045 | 0.809 | 0.956 | 1.000 |
| S016 | 20 | 2,175 | 1.174 | 0.357 | 1.012 | 0.976 | 1.000 |
| S021 | 20 | 1,592 | 0.316 | 0.572 | 0.697 | 0.916 | 1.000 |
| S026 | 20 | 1,900 | 9.448 | 1.954 | 1.398 | 1.156 | 1.000 |
| S031 | 20 | 2,628 | 0.122 | 0.796 | 0.945 | 0.934 | 1.000 |
| S036 | 20 | 21,366 | 1.915 | 1.108 | 0.949 | 0.853 | 1.000 |
| S041 | 20 | 458 | 1.670 | 1.277 | 1.086 | 1.011 | 1.000 |
| S046 | 20 | 873 | 0.563 | 0.889 | 0.615 | 1.050 | 1.000 |

### Size decisions

| firm_id | perturbation | fraction | x_mn | n | status | reason |
|---|---|---|---|---|---|---|
| L001 | cash | – | – | 40 | excluded | precision bound 351,034,918 exceeds upper bound 57,856,378 (KRW mn) at n_max |
| L001 | non_operating | – | – | 40 | excluded | precision bound 351,034,918 exceeds upper bound 190,622,702 (KRW mn) at n_max |
| L006 | cash | – | – | 40 | excluded | precision bound 31,158,971 exceeds upper bound 7,713,356 (KRW mn) at n_max |
| L006 | non_operating | – | – | 40 | excluded | precision bound 31,158,971 exceeds upper bound 14,820,006 (KRW mn) at n_max |
| L011 | cash | – | – | 40 | excluded | precision bound 11,759,909 exceeds upper bound 3,458,218 (KRW mn) at n_max |
| L011 | non_operating | 0.196 | 19,203,852 | 15 | increased_n |  |
| L016 | cash | 0.103 | 5,545,920 | 25 | increased_n |  |
| L016 | non_operating | 0.163 | 8,768,869 | 10 | ok |  |
| L021 | cash | 0.106 | 272,409 | 25 | increased_n |  |
| L021 | non_operating | 0.168 | 430,716 | 10 | ok |  |
| L026 | cash | – | – | 40 | excluded | precision bound 22,659,979 exceeds upper bound 3,801,455 (KRW mn) at n_max |
| L026 | non_operating | – | – | 40 | excluded | precision bound 22,659,979 exceeds upper bound 3,801,455 (KRW mn) at n_max |
| L031 | cash | – | – | 10 | excluded | non-positive equity value or share count |
| L031 | non_operating | – | – | 10 | excluded | non-positive equity value or share count |
| L036 | cash | – | – | 40 | excluded | precision bound 6,517,050 exceeds upper bound 3,232,697 (KRW mn) at n_max |
| L036 | non_operating | – | – | 40 | excluded | precision bound 6,517,050 exceeds upper bound 3,232,697 (KRW mn) at n_max |
| L041 | cash | – | – | 40 | excluded | precision bound 3,352,744 exceeds upper bound 1,171,466 (KRW mn) at n_max |
| L041 | non_operating | – | – | 40 | excluded | precision bound 3,352,744 exceeds upper bound 2,973,183 (KRW mn) at n_max |
| L046 | cash | 0.131 | 1,525,134 | 30 | increased_n |  |
| L046 | non_operating | 0.186 | 2,156,866 | 15 | increased_n |  |
| S001 | cash | – | – | 40 | excluded | precision bound 50,056 exceeds upper bound 906 (KRW mn) at n_max |
| S001 | non_operating | – | – | 40 | excluded | precision bound 50,056 exceeds upper bound 906 (KRW mn) at n_max |
| S006 | cash | – | – | 10 | excluded | non-positive equity value or share count |
| S006 | non_operating | – | – | 10 | excluded | non-positive equity value or share count |
| S011 | cash | – | – | 40 | excluded | precision bound 71,030 exceeds upper bound 9,840 (KRW mn) at n_max |
| S011 | non_operating | – | – | 40 | excluded | precision bound 71,030 exceeds upper bound 12,360 (KRW mn) at n_max |
| S016 | cash | – | – | 40 | excluded | precision bound 50,105 exceeds upper bound 7,017 (KRW mn) at n_max |
| S016 | non_operating | – | – | 40 | excluded | precision bound 50,105 exceeds upper bound 7,628 (KRW mn) at n_max |
| S021 | cash | – | – | 40 | excluded | precision bound 58,506 exceeds upper bound 2,096 (KRW mn) at n_max |
| S021 | non_operating | – | – | 40 | excluded | precision bound 58,506 exceeds upper bound 33,138 (KRW mn) at n_max |
| S026 | cash | – | – | 10 | excluded | non-positive equity value or share count |
| S026 | non_operating | – | – | 10 | excluded | non-positive equity value or share count |
| S031 | cash | – | – | 10 | excluded | non-positive equity value or share count |
| S031 | non_operating | – | – | 10 | excluded | non-positive equity value or share count |
| S036 | cash | – | – | 40 | excluded | precision bound 253,947 exceeds upper bound 10,265 (KRW mn) at n_max |
| S036 | non_operating | – | – | 40 | excluded | precision bound 253,947 exceeds upper bound 23,717 (KRW mn) at n_max |
| S041 | cash | – | – | 40 | excluded | precision bound 21,830 exceeds upper bound 5,895 (KRW mn) at n_max |
| S041 | non_operating | – | – | 40 | excluded | precision bound 21,830 exceeds upper bound 5,895 (KRW mn) at n_max |
| S046 | cash | – | – | 40 | excluded | precision bound 63,792 exceeds upper bound 20,490 (KRW mn) at n_max |
| S046 | non_operating | – | – | 40 | excluded | precision bound 63,792 exceeds upper bound 20,490 (KRW mn) at n_max |

### Response ratios

| firm_id | perturbation_type | perturbation_params | R | ci_lo | ci_hi |
|---|---|---|---|---|---|
| L001 | cash | {"dividend_line": "cf_008", "dps_delta": 1456.1673511693464, "x_mn": 8486265.1} | -8.665 | -32.066 | 10.871 |
| L001 | cash | {"dividend_line": "cf_008", "dps_delta": 3640.4183779233663, "x_mn": 21215662.75} | -0.248 | -6.169 | 16.079 |
| L001 | cash | {"dividend_line": "cf_008", "dps_delta": 7280.836755846733, "x_mn": 42431325.5} | -1.099 | -4.157 | 0.547 |
| L006 | cash | {"dividend_line": "cf_018", "dps_delta": 18824.363302785674, "x_mn": 968490.6768} | 61.037 | 39.542 | 84.493 |
| L006 | cash | {"dividend_line": "cf_018", "dps_delta": 3764.872660557135, "x_mn": 193698.13536} | 170 | 110 | 284 |
| L006 | cash | {"dividend_line": "cf_018", "dps_delta": 9412.181651392837, "x_mn": 484245.3384} | 88.296 | 39.875 | 156 |
| L011 | cash | {"dividend_line": "cf_017", "dps_delta": 15388.985932435535, "x_mn": 2495594.6227061} | 4.326 | 0.957 | 9.743 |
| L011 | cash | {"dividend_line": "cf_017", "dps_delta": 6155.594372974214, "x_mn": 998237.84908244} | 2.708 | -7.248 | 13.634 |
| L016 | cash | {"dividend_line": "cf_019", "dps_delta": 18439.629699571622, "x_mn": 2758195.6984245} | 1.174 | -0.040 | 3.153 |
| L016 | cash | {"dividend_line": "cf_019", "dps_delta": 3687.9259399143234, "x_mn": 551639.1396849} | 6.405 | -0.858 | 15.163 |
| L016 | cash | {"dividend_line": "cf_019", "dps_delta": 37076.6696455575, "x_mn": 5545919.97748516} | 0.771 | 0.194 | 1.553 |
| L016 | cash | {"dividend_line": "cf_019", "dps_delta": 9219.814849785811, "x_mn": 1379097.84921225} | -1.259 | -2.881 | 1.488 |
| L021 | cash | {"dividend_line": "cf_009", "dps_delta": 145.5573371387866, "x_mn": 13806.55039074} | 25.161 | 13.007 | 39.726 |
| L021 | cash | {"dividend_line": "cf_009", "dps_delta": 2871.9039367354844, "x_mn": 272408.7098549788} | 1.044 | 0.730 | 1.668 |
| L021 | cash | {"dividend_line": "cf_009", "dps_delta": 363.8933428469665, "x_mn": 34516.37597685} | 5.558 | 2.684 | 7.912 |
| L021 | cash | {"dividend_line": "cf_009", "dps_delta": 727.786685693933, "x_mn": 69032.7519537} | 3.174 | 1.813 | 4.620 |
| L026 | cash | {"dividend_line": "cf_015", "dps_delta": 23264.280185863223, "x_mn": 1642280.0} | 6.768 | 1.054 | 11.731 |
| L026 | cash | {"dividend_line": "cf_015", "dps_delta": 46528.560371726446, "x_mn": 3284560.0} | 5.247 | 1.414 | 18.747 |
| L026 | cash | {"dividend_line": "cf_015", "dps_delta": 9305.712074345289, "x_mn": 656912.0} | 24.581 | 0.383 | 39.398 |
| L031 | cash | {"dividend_line": "cf_008", "dps_delta": 2286.5275535482497, "x_mn": 203377.90278550002} | -4.519 | -18.250 | 5.864 |
| L031 | cash | {"dividend_line": "cf_008", "dps_delta": 914.6110214192997, "x_mn": 81351.1611142} | 11.553 | -5.788 | 19.964 |
| L036 | cash | {"dividend_line": "cf_012", "dps_delta": 1484.3822410092553, "x_mn": 165294.52} | 3.038 | -2.608 | 25.574 |
| L036 | cash | {"dividend_line": "cf_012", "dps_delta": 3710.955602523139, "x_mn": 413236.30000000005} | -1.866 | -5.141 | 2.486 |
| L036 | cash | {"dividend_line": "cf_012", "dps_delta": 7421.911205046278, "x_mn": 826472.6000000001} | 0.939 | 0.791 | 1.870 |
| L041 | cash | {"dividend_line": "cf_020", "dps_delta": 1967.9234450686574, "x_mn": 335421.70205} | 4.778 | -1.890 | 34.097 |
| L041 | cash | {"dividend_line": "cf_020", "dps_delta": 3935.846890137315, "x_mn": 670843.4041} | 2.638 | 0.032 | 4.893 |
| L041 | cash | {"dividend_line": "cf_020", "dps_delta": 787.169378027463, "x_mn": 134168.68082} | -0.588 | -29.111 | 22.424 |
| L046 | cash | {"dividend_line": "cf_011", "dps_delta": 12819.75788941477, "x_mn": 991610.6572212} | -1.041 | -1.907 | 0.245 |
| L046 | cash | {"dividend_line": "cf_011", "dps_delta": 19717.26981820399, "x_mn": 1525134.4878502649} | 0.957 | -0.657 | 1.583 |
| L046 | cash | {"dividend_line": "cf_011", "dps_delta": 2563.951577882954, "x_mn": 198322.13144424} | 3.068 | -6.185 | 6.967 |
| L046 | cash | {"dividend_line": "cf_011", "dps_delta": 6409.878944707385, "x_mn": 495805.3286106} | -0.700 | -2.147 | 0.986 |
| S001 | cash | {"dividend_line": "cf_p00", "dps_delta": 115.37804119815601, "x_mn": 1535.4760093000002} | 22.716 | -22.307 | 60.547 |
| S001 | cash | {"dividend_line": "cf_p00", "dps_delta": 23.0756082396312, "x_mn": 307.09520186000003} | 35.795 | -156 | 309 |
| S001 | cash | {"dividend_line": "cf_p00", "dps_delta": 57.689020599078006, "x_mn": 767.7380046500001} | 106 | -15.480 | 125 |
| S006 | cash | {"dividend_line": "cf_p00", "dps_delta": 11.120366439003815, "x_mn": 404.73764646000006} | -36.167 | -65.079 | 49.998 |
| S006 | cash | {"dividend_line": "cf_p00", "dps_delta": 27.80091609750954, "x_mn": 1011.8441161500001} | 0.592 | -5.127 | 13.872 |
| S006 | cash | {"dividend_line": "cf_p00", "dps_delta": 55.60183219501908, "x_mn": 2023.6882323000002} | -6.800 | -17.471 | 1.539 |
| S011 | cash | {"dividend_line": "cf_p00", "dps_delta": 136.4523937927739, "x_mn": 3180.0976768} | -0.912 | -3.044 | 4.532 |
| S011 | cash | {"dividend_line": "cf_p00", "dps_delta": 27.290478758554784, "x_mn": 636.0195353600001} | -2.735 | -13.775 | 17.882 |
| S011 | cash | {"dividend_line": "cf_p00", "dps_delta": 68.22619689638695, "x_mn": 1590.0488384} | -2.304 | -79.308 | 29.621 |
| S016 | cash | {"dividend_line": "cf_019", "dps_delta": 168.1102504709021, "x_mn": 3454.7414649} | 14.617 | 6.973 | 27.355 |
| S016 | cash | {"dividend_line": "cf_019", "dps_delta": 336.2205009418042, "x_mn": 6909.4829298} | 2.634 | -3.911 | 11.040 |
| S016 | cash | {"dividend_line": "cf_019", "dps_delta": 67.24410018836083, "x_mn": 1381.89658596} | 23.292 | 2.081 | 57.545 |
| S021 | cash | {"dividend_line": "cf_p00", "dps_delta": 36.829023738915275, "x_mn": 1210.78232962} | -9.928 | -58.240 | 36.615 |
| S026 | cash | {"dividend_line": "cf_p00", "dps_delta": 152.6400874827162, "x_mn": 5288.7938788500005} | 1.316 | -1.337 | 22.672 |
| S026 | cash | {"dividend_line": "cf_p00", "dps_delta": 305.2801749654324, "x_mn": 10577.587757700001} | -1.158 | -2.052 | 0.177 |
| S026 | cash | {"dividend_line": "cf_p00", "dps_delta": 61.05603499308649, "x_mn": 2115.51755154} | -3.601 | -9.021 | 1.335 |
| S031 | cash | {"dividend_line": "cf_010", "dps_delta": 728.8517920466521, "x_mn": 8470.98957544} | -1.375 | -5.826 | 3.792 |
| S036 | cash | {"dividend_line": "cf_p00", "dps_delta": 222.61552456526258, "x_mn": 2366.5775567} | 11.473 | 1.705 | 118 |
| S036 | cash | {"dividend_line": "cf_p00", "dps_delta": 445.23104913052515, "x_mn": 4733.1551134} | 2.852 | 0.155 | 59.191 |
| S036 | cash | {"dividend_line": "cf_p00", "dps_delta": 89.04620982610501, "x_mn": 946.63102268} | 61.057 | 2.011 | 324 |
| S041 | cash | {"dividend_line": "cf_p00", "dps_delta": 11.541370045734032, "x_mn": 491.86683086} | -1.402 | -62.432 | 61.905 |
| S041 | cash | {"dividend_line": "cf_p00", "dps_delta": 28.85342511433508, "x_mn": 1229.66707715} | 9.396 | 0.022 | 31.169 |
| S041 | cash | {"dividend_line": "cf_p00", "dps_delta": 57.70685022867016, "x_mn": 2459.3341543} | 4.565 | -1.946 | 15.468 |
| S046 | cash | {"dividend_line": "cf_p00", "dps_delta": 105.4006552727567, "x_mn": 6890.5105005000005} | -0.212 | -2.117 | 2.240 |
| S046 | cash | {"dividend_line": "cf_p00", "dps_delta": 210.8013105455134, "x_mn": 13781.021001000001} | 0.362 | -1.180 | 1.772 |
| S046 | cash | {"dividend_line": "cf_p00", "dps_delta": 42.16026210910268, "x_mn": 2756.2042002000003} | -0.043 | -5.493 | 7.741 |

### CB dilution (E8)

| firm_id | N_v1 | theory_V0 | R_dil_V0 | R_dil_V2 | R_dil_V3 | itm_agent |
|---|---|---|---|---|---|---|
| S001 | 13,335,216 | 0.000 | – | – | 1.347 | True |
| S006 | 37,673,903 | 0.000 | – | – | – | False |
| S011 | 23,307,078 | -221 | -1.014 | -0.310 | 0.010 | True |
| S016 | 20,601,646 | -812 | 2.806 | 2.000 | 1.429 | True |
| S021 | 32,875,765 | -975 | 1.068 | 1.548 | 0.609 | True |
| S026 | 34,648,787 | 0.000 | – | – | – | False |
| S031 | 11,690,462 | 0.000 | – | – | – | False |
| S036 | 10,630,784 | -3,846 | 5.902 | 3.361 | 4.754 | True |
| S041 | 42,620,470 | 0.000 | – | – | – | False |
| S046 | 65,374,456 | -87.966 | -1.194 | -0.788 | – | True |

### Anomaly-flag rate by perturbation

| perturbation_type | anomaly_rate |
|---|---|
| cash | 0.535 |
| cb_v0 | 0.740 |
| cb_v1 | 0.870 |
| cb_v2 | 0.730 |
| cb_v3 | 0.789 |
| none | 0.561 |
| scale | 0.576 |

### Main-run cost re-estimate

| schema | main_calls | mean_tokens_in | mean_tokens_out | usd |
|---|---|---|---|---|
| valuation | 36780 | 5,903 | 1,102 | 37.919 |
| quiz | 450 | 367 | 81.700 | 0.031 |


## Pilot history

### Round 1 (2026-10-05): prompt v1 + structure P

Pilot L (1,230 calls): G1 PASS 99.8%; G2 FAIL (median ε 81%; the error is in the discounting step: EV gaps 20–115% while the bridge and division are correct); G4 FAIL 0/10; unit slips (amounts ÷ 1000, sometimes shares ÷ 1000) in 24% of E0 runs for the largest firms; G3 not interpretable.

### Round 2 (2026-10-06): prompt v1.1 + structure T

Fixes for the two round-1 problems:
- **Unit slips** → prompt v1.1 adds explicit unit rules (copy amounts in KRW million as printed; shares as printed; Korean rationale). Verified on the dev set with two scaled-up dev packages (X011, X012: revenue ≈ KRW 220–300 trillion), which reproduce the slips under v1 (33–47% of runs) and show 0–20% under v1.1·P and **0%** under v1.1·T.
- **Discounting errors** → structure T (Python computes FCFF, discounting, bridge, per-share value).

Pilot L re-run with T + v1.1 (1,230 calls): G1 99.9%, **G2 PASS** (ε = 0 by construction), unit slips **0%**, G3 mean β_A − β_C = −0.08 (90% CI [−0.15, −0.02], 8 firms with positive values). **G4 still fails (0/10).**

Why G4 still fails:
1. **D&A is missing from 131 of 150 packages** (DART structured cash-flow data give only the total "조정" line), so the model invents D&A in each run (Samsung Electronics: 0 to 55 trillion KRW against ~48 trillion capex), which swings FCFF. Re-computing the same T runs with D&A = capex and ΔNWC = 0 cuts the run-to-run CV from 190% → 39% (L001), 39% → 5% (L011), 45% → 8% (L041), 76% → 18% (L006).
2. **The §6.8 parameters are very strict for LLM noise.** With s* = 0.1 and the 10% cap, a firm passes only if CV ≤ 3.2% at n = 20 (4.5% at n = 40). Even after (1) most firms have CV 4–40%.
   | s* | cap | max CV, n = 20 | max CV, n = 40 |
   |---|---|---|---|
   | 0.10 | 10% | 3.2% | 4.5% |
   | 0.10 | 20% | 6.3% | 8.9% |
   | 0.20 | 10% | 6.3% | 8.9% |
   | 0.25 | 20% | 15.8% | 22.4% |
3. Two firms (L026, L031) have non-positive baseline values in every run (D7.5).

Decisions needed (design, before the preregistration): (a) a D&A convention in the tool prompt (D&A = capex, ΔNWC from history or 0) or adding D&A to the packages from the annual-report notes; (b) relaxing s* and/or the cap, or accepting E3 on fewer firms; (c) D7.5 for non-positive baselines.

### Round 3 (2026-10-06): prompt v1.2 (D&A = capex) + structure T, pilot L + S

10 L + 10 S firms, 3,420 calls (all valid, about $4).

| Gate | Result |
|---|---|
| G1 | PASS |
| G2 | PASS |
| G3 | PASS: mean β_A − β_C = 0.18, which meets the \|mean\| ≥ 0.10 criterion; CI [−0.13, 0.57] |
| G4 | FAIL: 0/20 at n ≤ 20, 3/20 at n ≤ 40 |
| G5 | PASS: 50 ITM firms, E8 390/390 valid |

D&A = capex compliance: 68% of E0 runs.

Noise compared with round 2: large-cap CV fell for most firms (L001 190% → 33%, L011 39% → 11%). Most small caps still exceed 100%, because loss-making firms get margins of −5%, 0% or +5%, which flips the sign of the value. Re-computing with D&A = capex and ΔNWC = 0 enforced would make only 7 of 20 firms measurable. The remaining noise is therefore assumption uncertainty, not something the input rules can remove.

User decision (D7.8): adopt the G4 fallback. E3 runs at the rule size only for accepted firms; tiers run for all firms.
