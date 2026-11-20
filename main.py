import pandas as pd
import numpy as np
import argparse
import os

from parameters import grid, battery
from plot_class import EnergyPlotter
from preprocess_class import Test_Customer_Data
from optimizer_class import BatteryOptimizer

np.random.seed(42)

# Fix assumptions via arguments
parser = argparse.ArgumentParser(description="Fix configuration.")
parser.add_argument(
    "--timezone",
    type=str,
    default="Europe/Berlin",
    help="Choose time zone of results and plots. Default is Europe/Berlin since the test customer is probably located there.",
)

parser.add_argument(
    "--assume_mislabel",
    action="store_true",
    help="If mislabeling of consumption data timestamp is assumed and UTC is used instead. Thus, PV & consumption data are manually aligned in time.",
)

args = parser.parse_args()

date = pd.Timestamp("2026-06-15T00:00:00").tz_localize("Europe/Berlin")

test_customer_data = Test_Customer_Data(
    consumption_file_path="fix_consumption_data.csv",
    pv_file_path="pv_data.csv",
    target_timezone=args.timezone,
    grid_dict=grid,
    grid_start_date=date,
    assume_mislabel=args.assume_mislabel,
)

df_preprocessed = test_customer_data.preprocess_data()

# Create folder to save plots in
os.makedirs("plots", exist_ok=True)

# Initialize plotter
plotter = EnergyPlotter(
    timezone=args.timezone,
    date=date,
    x_min=df_preprocessed.index.min(),
    x_max=df_preprocessed.index.max(),
    assume_mislabel=args.assume_mislabel,
)

# Initialize optimizer
optimizer = BatteryOptimizer(
    battery_params=battery, penalty_weight=0.1, balanced=False, deg_cost=0.03
)

###########################################################
# Scenario 1
# PV + Consumption + Grid without battery
# -> no optimization, for comparison
###########################################################

total_price = df_preprocessed["price_eur"].sum()
print(
    f"Total cost without the additional battery for the given 24h: {total_price:.2f} €."
)

plotter.plot_scenario_1(df_preprocessed, df_preprocessed, total_price)

###################################################
# Scenario 2
# PV + Consumption + Grid + Battery
# -> optimize schedule for battery (charging/discharging)
###################################################

results_df = optimizer.optimize_schedule(df=df_preprocessed, printing=True)
total_cost_optimized = BatteryOptimizer.calculate_scenario_costs(
    df_results=results_df,
    demand_price=df_preprocessed["demand_price_eur_per_kwh"],
    supply_price=df_preprocessed["supply_price_eur_per_kwh"],
)

print("-" * 50)
print(f"Total cost without battery:   {total_price:.2f} €")
print(
    f"Total cost with optimized battery: {total_cost_optimized:.2f} €"
)

# Save the battery schedule (charge > 0, discharge < 0) in 15 minute resolution
os.makedirs("results", exist_ok=True)
schedule = results_df[
    [
        "battery_schedule_kw",
        "battery_charge_power_kw",
        "battery_discharge_power_kw",
        "soc_kwh",
        "net_demand_kw_pos",
        "net_demand_kw_neg",
    ]
].rename(
    columns={
        "soc_kwh": "soc_at_interval_start_kwh",
        "net_demand_kw_pos": "grid_import_kw",
        "net_demand_kw_neg": "grid_export_kw",
    }
)
# Round away solver noise; adding 0.0 turns -0.0 into 0.0
schedule = schedule.round(3) + 0.0
suffix = "_mislabel" if args.assume_mislabel else ""
schedule_file = f"results/battery_schedule_{args.timezone[:3]}{suffix}.csv"
schedule.to_csv(schedule_file)
print(f"Battery schedule saved to {schedule_file}")

plotter.plot_scenario_2(df_preprocessed, results_df, total_cost_optimized)

###################################################
# Scenario 3
# PV + Consumption + Grid + Battery
# Influence of uncertainty on predicted PV + consumption power
# on battery schedule
#
# Calculate n_scenarios schedules for fluctuating PV and consumption data
# using a normal distribution with standard deviation pv_std and load_std, respectively
###################################################

mc_schedules, mc_socs, mc_pvs, mc_loads, mc_imports, mc_costs = (
    optimizer.run_monte_carlo_sensitivity(
        df_base=df_preprocessed, n_scenarios=30, pv_std=0.10, load_std=0.10
    )
)

stats = {}
for name, df in zip(
    ["schedule", "soc", "pv", "load", "import"],
    [mc_schedules, mc_socs, mc_pvs, mc_loads, mc_imports],
):
    stats[f"{name}_mean"] = df.mean(axis=1)
    stats[f"{name}_min"] = df.min(axis=1)
    stats[f"{name}_max"] = df.max(axis=1)

plotter.plot_scenario_3(df_preprocessed, stats)

###################################################
# Scenario 4
# PV + Consumption + Grid + Battery
# How would an optimization including uncertainties work?
# -> try Model Predictive Control (MPC)
#
# We only have 24 hour of data, just assume 3 days in the row
# with same PV & consumption to perform MPC for a 24h period
###################################################

df_extended_actual = pd.concat([df_preprocessed] * 3)
df_extended_actual.index = [
    df_preprocessed.index[0] + pd.Timedelta(minutes=15) * i
    for i in range(len(df_extended_actual))
]

df_extended_noisy = BatteryOptimizer.generate_uncertain_predictions(
    df_extended_actual, pv_std=0.10, load_std=0.10
)
results_df_mpc = optimizer.run_mpc_simulation(
    df_actual=df_extended_actual, pv_std=0.10, load_std=0.10, horizon_hours=24
)

# clip results and noisy data to first 24h
results_df_mpc_24h = results_df_mpc.iloc[:96].copy()
df_noisy_24h = df_extended_noisy.iloc[:96].copy()

total_cost_mpc = BatteryOptimizer.calculate_scenario_costs(
    df_results=results_df_mpc_24h,
    demand_price=results_df_mpc_24h["demand_price_eur_per_kwh"],
    supply_price=results_df_mpc_24h["supply_price_eur_per_kwh"],
)

print(f"Total cost with MPC optimized battery: {total_cost_mpc:.2f} €")

plotter.plot_scenario_4(results_df_mpc_24h, df_noisy_24h)
