# NEMDE Approximation
Australia's National Electricity Dispatch Engine (NEMDE) determines regional electricity prices and sets dispatch targets for generators and loads in Australia's National Electricity Market (NEM). This repository contains a model that seeks to approximate the operation of NEMDE. If you just want to interact with the model, and are less interested in model development, please see [https://github.com/akxen/nemde-api](https://github.com/akxen/nemde-api).

Key elements of the model's formulation have been inferred by analysing publicly available documents released by the Australian Energy Market Operator (AEMO). As NEMDE's mathematical formulation is not publicly available it is not possible to validate the approximated model's mathematical formulation directly. Instead, a data driven approach is used to evaluate the model's performance. This involves passing the approximate model of NEMDE historical case files describing the NEM's state, with the model using these parameters to formulate and solve a mathematical program. Outputs from the approximated model consist of prices and dispatch targets which are then compared with historical solutions reported by NEMDE. Close correspondence between solutions obtained from the approximate model and those reported by NEMDE indicates good model performance.

A Docker container is used run a MySQL database to store historical NEMDE case files and handle results outputted during validation runs. Use the following steps to test the model on your local machine.

## Steps to evaluate model
1. Clone the repository:
```
git clone https://github.com/akxen/nemde.git
```

2. Setup MySQL container environment variables. Rename `mysql/mysql-template.env` to `mysql/mysql.env` and set `MYSQL_PASSWORD` and `MYSQL_ROOT_PASSWORD` variables.

3. Setup NEMDE container environment variables. Rename `config/nemde-template.env` to `config/nemde.env` and update entries. Ensure `MYSQL_PASSWORD` corresponds to `MYSQL_ROOT_PASSWORD` specified in `config/mysql.env`.

4. Use `casefiles/zipped/download_casefiles.sh` to download historical NEMDE case files. The `TEST_YEAR` and `TEST_MONTH` variables within `config/nemde.env` should correspond to the monthly archive you have downloaded.
 
5. Run `./run_tests.sh` to test the model using the settings specified within `config/nemde.env`. **It may take a some time (1-2 hours) to build the containers and upload NEMDE case files in the MySQL database the first time you run this command**. Logs are stored in `~/logs` by default. Update `run_tests.sh` to change the output directory.