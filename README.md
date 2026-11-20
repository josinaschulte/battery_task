# Battery task

This repository contains a Python project to solve the energy management task outlined in `readme.txt`. The goal is to determine an optimal 24-hour operational schedule for a battery storage system consisting of a consumer which is connected to a PV system, the power grid as well as an additional battery. The model minimizes energy costs while prioritizing the reduction of energy supplied to the grid.

## Overview

- **Data:** The 24-hour data for predicted PV power is given in `pv_data.csv` and predicted consumption in `fix_consumption_data.csv`. The prices for grid supply and demand, as well as the properties of the battery, are defined in `parameters.py`.
- **Data Preprocessing:**  Processing for raw consumption and PV data, converts units to kW, and aligns time zones and upsamples the data for a consistent 15-minute frequency (`preprocess_class.py`).
- **Optimization:** Uses `oemof.solph` to model the energy system and calculate a cost-optimal schedule (`optimizer_class.py`).
- **Sensitivity Analysis & MPC:** Mini Monte Carlo analysis analyzing forecast uncertainties and a basic Model Predictive Control (MPC) simulation (`optimizer_class.py`).
- **Visualization:** Generation of plots of power flows, battery state of charge (SOC), and grid prices (`plot_class.py`).

## Prerequisites

### 1. External Solver
`oemof.solph` requires an external solver for linear programming, e.g. CBC.

### 2. LaTeX for Plotting
The visualization script uses a custom matplotlib style (`latex_style.mplstyle`). This requires a local LaTeX installation to render the plots properly.

## Installation and Requirements
This project uses an `environment.yml` file to manage its dependencies, including Python, the external CBC solver, and the required Python packages.

### 1. Clone the repository
```bash
git clone git@github.com:josinaschulte/battery_task.git
cd battery_task
```

### 2. Create and activate the environment
```bash
conda env create -f environment.yml
conda activate battery_task
```

### 3. Run the code
```bash
python main.py
```


## Usage
The solution to the task is separated in four parts based on the assumptions outlined in the following.

### Assumptions

- **Time zones:**
Due to a time zone mismatch between the PV data (*UTC*) and the consumption data (*Europe/Berlin local*), two options are being considered to fulfill the customer's request for a 24-hour battery schedule: either prefill the PV data with 0s for 2 hours during the night, as no PV is expected anyway, or assume a mislabelling of the consumption data and shift it to UTC as well. The fact that the test customer is located in the Europe/Berlin time zone is verified by the peak in the given PV data at noon local Berlin time. The script output can be in Europe/Berlin local time or UTC: this is managed with the argument `--timezone`. The default is Europe/Berlin local time. If the consumption data are to be shifted to UTC, the argument `--assume_mislabel` can be used. The default is no shift in time and the prefilling with 0s.

- **Battery state of charge at the end of the day:**
The battery has to end the 24 hours with the same state of charge it started with (10 kWh, `balanced=True`). Otherwise the optimizer would use up the energy that is already stored in the battery at the start of the day, and the reported savings compared to the scenario without battery would include this extra energy. With this constraint, the savings only result from operating the battery within the day.

- **Battery degradation:**
The _battery degradation costs_ applied in this model are 0.03€/kWh as a rough estimate. This also suppresses sharp jumps in the battery schedule.

### 1. Scenario

- **PV + Consumption + Grid without Battery:** This is the basic setup for the test customer. Here, an overview of the situation without the additional battery in the system is produced. To this end, plots of the data are generated. The PV and consumption power as a function of time are plotted, as well as the net demand which is calculated by subtracting the consumption demand from the PV. Additionally, the grid price is shown, as well as the net cost as a function of time and the total sum for the given 24 hours.

### 2. Scenario

- **PV + Consumption + Grid + Battery:** Here, the battery is included in the system and the schedule for the battery charging and discharging to optimize costs in conjunction with minimal supply to the grid is determined. Therefore, the energy system is defined in `oemof` and an additional _penalty weight_ for the supply to the grid is added. The penalty weight was chosen to be 0.1€/kWh. To make sure the battery never charges and discharges at the same time, the charge and discharge flows each get a binary on/off variable, and an additional constraint allows at most one of them to be on in every time step. The battery schedule is saved as a CSV file in `results/` (e.g. `results/battery_schedule_Eur.csv`) in 15-minute resolution. Its columns are the schedule `battery_schedule_kw` (charging > 0, discharging < 0), the charge and discharge power split, the battery state of charge at the start of each interval in kWh, and the resulting grid import and export in kW. Each timestamp marks the start of its 15-minute interval. The results for the schedule of the battery are shown in a plot as well as the net cost including the battery, for comparison to the first scenario without the battery. Additionally, an _energy dashboard_ is created with an overview of power consumption and generation, the battery schedule, as well as the grid price for the 24 hours.


### 3. Scenario

- **PV + Consumption + Grid + Battery - Uncertainties:** Here, the influence of uncertainties in the prediction of the PV and consumption power is looked at. Therefore, `n_scenarios` schedules for fluctuating PV and consumption data are calculated using normal distributions with standard deviation `pv_std` and `load_std`, respectively, both clipped to values larger than zero. The default are `30` scenarios with `0.1` as standard deviation for PV and consumption power. The resulting _energy dashboard_ is plotted with bands representing the spread of all scenarios. The general schedule is relatively constant for uncertainties in this order of magnitude.

### 4. Scenario

- **PV + Consumption + Grid + Battery - MPC:** Here, predicting a schedule taking uncertainties into account is glanced at. Model Predictive Control (MPC) uses different realization of the system within the defined fluctuations and uses a new variation for the minimization in every scheduled time step. As the data only contains 24 hours and for a schedule of this length more data is needed for MPC, three identical days in a row were assumed and the uncertainties of 10% as in scenario 3. The final schedule is plotted in a dashboard. The general course for the battery schedule is similar to the baseline scenario, but the pre-charging shortly before sunrise as seen in the previous scenarios is suppressed when the exact PV generation is not certain.