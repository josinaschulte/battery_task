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

- **PV + Consumption + Grid + Battery:** Here, the battery is included in the system and the schedule for the battery charging and discharging to optimize costs in conjunction with minimal supply to the grid is determined. Therefore, the energy system is defined in `oemof` and an additional _penalty weight_ for the supply to the grid is added. The penalty weight was chosen to be 10 €/kWh. This is far above both grid prices, the demand price paid for energy taken from the grid (0.13–0.35 €/kWh) and the supply price received for energy fed into the grid (0.20 €/kWh). So no cost saving can outweigh supplying energy to the grid, which makes minimizing the supply the higher priority, as requested. With a penalty below 0.07 €/kWh (supply price 0.20 minus the lowest demand price 0.13), buying energy from the grid and selling it back at the same time would earn money, and the optimization would become unbounded. The penalty weight and the degradation costs only steer the optimization. The reported costs are the grid costs only: energy taken from the grid at the demand price minus energy supplied to the grid at the supply price. To make sure the battery never charges and discharges at the same time, the charge and discharge flows each get a binary on/off variable, and an additional constraint allows at most one of them to be on in every time step. The battery schedule is saved as a CSV file in `results/` (e.g. `results/battery_schedule_Eur.csv`) in 15-minute resolution. Its columns are the schedule `battery_schedule_kw` (charging > 0, discharging < 0), the charge and discharge power split, the battery state of charge at the start of each interval in kWh, and the resulting grid import and export in kW. Each timestamp marks the start of its 15-minute interval. Since the grid prices are constant within each hour, there are several equally cheap schedules, and the solver may pick a different one between runs (e.g. swapping the charging power of two time steps within the same hour); the costs stay the same. The results for the schedule of the battery are shown in a plot as well as the net cost including the battery, for comparison to the first scenario without the battery. Additionally, an _energy dashboard_ is created with an overview of power consumption and generation, the battery schedule, as well as the grid price for the 24 hours.


### 3. Scenario

- **PV + Consumption + Grid + Battery - Uncertainties:** Here, the influence of uncertainties in the prediction of the PV and consumption power is looked at. Therefore, `n_scenarios` schedules for fluctuating PV and consumption data are calculated using normal distributions with standard deviation `pv_std` and `load_std`, respectively, both clipped to values larger than zero. The default are `30` scenarios with `0.1` as standard deviation for PV and consumption power. The resulting _energy dashboard_ is plotted with bands representing the spread of all scenarios. The general schedule is relatively constant for uncertainties in this order of magnitude.

### 4. Scenario

- **PV + Consumption + Grid + Battery - MPC:** Here, operating the battery without perfect foresight is glanced at, using a simple Model Predictive Control (MPC) simulation:
  - Every 15 minutes, a new forecast is generated by adding noise to the actual PV and consumption data, with the same uncertainties of 10% as in scenario 3.
  - The battery schedule is optimized for this forecast from the current time step until the end of the day. As in scenario 2, the battery has to end the day with at least its initial state of charge (10 kWh), so the costs of both scenarios are comparable.
  - Of each plan, only the battery power for the current 15 minutes is used. The grid balances the difference between the forecast and the actual PV and consumption during these 15 minutes. In the next time step, a new plan is made with a new forecast.

  The resulting schedule is plotted in a dashboard together with the actual PV and consumption and the resulting grid import and supply. The general course is similar to scenario 2: the battery charges from the grid in the cheapest hour (05:00 to 06:00), stores the PV surplus around noon, discharges during the evening price peak and recharges to 10 kWh before midnight. With the fixed random seed, the total cost is about 15.0 €, compared to 14.34 € with perfect foresight (scenario 2) and 16.01 € without battery. The higher cost compared to scenario 2 is the price of the forecast uncertainty.

  **Limitations:** The MPC supplies about 10 kWh to the grid, although minimizing the supply has the highest priority. One reason is that the grid has to balance the forecast errors. The other is that when a plan expects more PV surplus than the battery can store, it discharges the battery into the grid early to make room, as this reduces the planned supply. Since the next forecast is different, this is often unnecessary. The forecast model is very simple: the noise is drawn independently for every time step, also for the current 15 minutes, which in reality would be known quite well. A more realistic forecast model, e.g. with forecast errors that change gradually over time, would reduce both effects. The results also depend on the random noise, so the numbers change with a different random seed.