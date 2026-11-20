import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from oemof import solph
from oemof.network.graph import create_nx_graph
import networkx as nx
import pyomo.environ as po


class BatteryOptimizer:
    def __init__(
        self,
        battery_params: dict,
        penalty_weight: float = 10.0,
        balanced: bool = False,
        deg_cost: float = 0.0,
    ):
        """
        Initializes the optimizer with standard parameters for the energy system.

        battery_params: containing SOC, (dis)charge efficiencies, capacity, dis(charge) power
        penalty_weight: extra cost in the optimization for exporting to the grid, in €/kWh
        balanced: if the battery final SOC should equal the initial SOC
        deg_cost: battery degradation cost, in €/kWh
        """
        self.battery = battery_params
        self.penalty_weight = penalty_weight
        self.balanced = balanced
        self.deg_cost = deg_cost

    def optimize_schedule(
        self,
        df: pd.DataFrame,
        initial_soc_override: float = None,
        final_soc_min_kwh: float = None,
        printing: bool = False,
    ) -> pd.DataFrame:
        """
        Optimize a battery schedule in 15-minute intervals using oemof.solph.

        initial_soc_override: SOC at the start of the schedule, in kWh (used by the MPC)
        final_soc_min_kwh: minimum SOC at the end of the schedule, in kWh.
            If given, it replaces the balanced condition (used by the MPC).
        """
        # Set the 15 minute frequency explicitly, oemof cannot infer it
        # for schedules shorter than 3 time steps
        timeindex = pd.DatetimeIndex(df.index, freq="15min")
        energysystem = solph.EnergySystem(timeindex=timeindex, infer_last_interval=True)
        b_el = solph.Bus(label="electricity")
        energysystem.add(b_el)

        demand_sink = solph.components.Sink(
            label="consumption",
            inputs={b_el: solph.Flow(fix=df["fixed_demand_kw"], nominal_capacity=1)},
        )

        pv_source = solph.components.Source(
            label="pv",
            outputs={b_el: solph.Flow(fix=df["pv_power_kw"], nominal_capacity=1)},
        )
        energysystem.add(demand_sink, pv_source)

        # Variable costs are given in €/kWh: oemof multiplies them with the
        # flow in kW and the length of the time step (0.25 h)
        grid_import = solph.components.Source(
            label="grid_demand",
            outputs={b_el: solph.Flow(variable_costs=df["demand_price_eur_per_kwh"])},
        )

        export_costs = self.penalty_weight - df["supply_price_eur_per_kwh"]
        grid_export = solph.components.Sink(
            label="grid_supply", inputs={b_el: solph.Flow(variable_costs=export_costs)}
        )

        energysystem.add(grid_import, grid_export)

        # Allow dynamic initial SOC for MPC simulations
        start_soc = (
            initial_soc_override
            if initial_soc_override is not None
            else self.battery["soc_initial_kwh"]
        )

        storage = solph.components.GenericStorage(
            label="battery",
            nominal_capacity=self.battery["capacity_kwh"],
            inputs={
                b_el: solph.Flow(
                    nominal_capacity=self.battery["charge_power_max_kw"],
                    maximum=1.0,
                    nonconvex=solph.NonConvex(),
                )
            },
            outputs={
                b_el: solph.Flow(
                    nominal_capacity=self.battery["discharge_power_max_kw"],
                    maximum=1.0,
                    nonconvex=solph.NonConvex(),
                    variable_costs=self.deg_cost,
                )
            },
            initial_storage_level=start_soc / self.battery["capacity_kwh"],
            min_storage_level=self.battery["soc_min_kwh"]
            / self.battery["capacity_kwh"],
            max_storage_level=self.battery["soc_max_kwh"]
            / self.battery["capacity_kwh"],
            inflow_conversion_factor=self.battery["eta_charge"],
            outflow_conversion_factor=self.battery["eta_discharge"],
            balanced=self.balanced if final_soc_min_kwh is None else False,
            loss_rate=0.0,
        )
        energysystem.add(storage)

        if printing:
            graph = create_nx_graph(energysystem)
            plt.figure(figsize=(6, 8))
            pos = {
                "pv": (0, 1),
                "battery": (-0.5, 0),
                "grid_supply": (0.5, 0.5),
                "electricity": (0, 0),
                "grid_demand": (0.5, -0.5),
                "consumption": (0, -1),
            }
            nx.draw(
                graph,
                pos=pos,
                with_labels=True,
                node_size=6000,
                node_color=plt.rcParams["axes.prop_cycle"].by_key()["color"][-1],
                edgecolors="black",
                linewidths=2,
                arrows=True,
                arrowsize=25,
                width=2,
            )
            plt.margins(0.06)
            plt.savefig("plots/energysystem_graph.png")
            plt.close()

        model = solph.Model(energysystem)

        # The battery cannot charge and discharge at the same time:
        # at most one of the binary on/off variables of the charge
        # and discharge flow can be 1 in every time step
        status = model.NonConvexFlowBlock.status

        def no_simultaneous_charge_discharge(m, t):
            return status[b_el, storage, t] + status[storage, b_el, t] <= 1

        model.no_simultaneous_charge_discharge = po.Constraint(
            model.TIMESTEPS, rule=no_simultaneous_charge_discharge
        )

        # Minimum SOC at the end of the schedule
        if final_soc_min_kwh is not None:
            model.final_soc_min = po.Constraint(
                expr=model.GenericStorageBlock.storage_content[
                    storage, model.TIMEPOINTS.at(-1)
                ]
                >= final_soc_min_kwh
            )

        model.solve(solver="cbc", solve_kwargs={"tee": printing})
        results = solph.processing.results(model)

        def get_flow(source, target):
            return results[(energysystem.groups[source], energysystem.groups[target])][
                "sequences"
            ]["flow"]

        results_df = pd.DataFrame(index=df.index)
        results_df["battery_charge_power_kw"] = get_flow("electricity", "battery")
        results_df["battery_discharge_power_kw"] = -get_flow("battery", "electricity")
        results_df["net_demand_kw_pos"] = get_flow("grid_demand", "electricity")
        results_df["net_demand_kw_neg"] = get_flow("electricity", "grid_supply")
        results_df["net_demand_kw"] = (
            results_df["net_demand_kw_pos"] - results_df["net_demand_kw_neg"]
        )
        results_df["soc_kwh"] = results[(energysystem.groups["battery"], None)][
            "sequences"
        ]["storage_content"]
        results_df["battery_schedule_kw"] = (
            results_df["battery_charge_power_kw"]
            + results_df["battery_discharge_power_kw"]
        )

        return results_df

    def run_monte_carlo_sensitivity(
        self,
        df_base: pd.DataFrame,
        n_scenarios: int = 30,
        pv_std: float = 0.10,
        load_std: float = 0.10,
    ):
        all_schedules, all_socs, all_pvs, all_loads, all_imports = (
            [],
            [],
            [],
            [],
            [],
        )

        for i in range(n_scenarios):
            df_noisy = self.generate_uncertain_predictions(
                df_base, pv_std=pv_std, load_std=load_std
            )
            res = self.optimize_schedule(df=df_noisy, printing=False)

            all_schedules.append(res["battery_schedule_kw"].rename(f"scenario_{i}"))
            all_socs.append(res["soc_kwh"].rename(f"scenario_{i}"))
            all_imports.append(res["net_demand_kw_pos"].rename(f"scenario_{i}"))
            all_pvs.append(df_noisy["pv_power_kw"].rename(f"scenario_{i}"))
            all_loads.append(df_noisy["fixed_demand_kw"].rename(f"scenario_{i}"))

        return (
            pd.concat(all_schedules, axis=1),
            pd.concat(all_socs, axis=1),
            pd.concat(all_pvs, axis=1),
            pd.concat(all_loads, axis=1),
            pd.concat(all_imports, axis=1),
        )

    def run_mpc_simulation(
        self,
        df_actual: pd.DataFrame,
        pv_std: float,
        load_std: float,
    ) -> tuple[pd.DataFrame, float]:
        """
        Simulate the battery operation with Model Predictive Control (MPC).

        In every 15 minute step, a new forecast is generated by adding noise
        to the actual PV and consumption data, and the battery schedule is
        optimized for this forecast from the current step until the end of
        the day. As in the perfect foresight optimization, the battery has to
        end the day with at least its initial SOC.

        Of each plan, only the battery power for the current 15 minutes is
        used. The grid balances the difference between the forecast and the
        actual PV and consumption during these 15 minutes. In the next step,
        a new plan is made with a new forecast.

        Returns the realized schedule (SOC at the start of each interval)
        and the SOC at the end of the day in kWh.
        """
        actual_soc = self.battery["soc_initial_kwh"]
        realized_results = []

        for t in range(len(df_actual)):
            current_time = df_actual.index[t]
            # Noise is generated for the whole day and then cut to the remaining
            # steps, so its size does not depend on the remaining PV generation
            df_window_noisy = self.generate_uncertain_predictions(
                df_actual, pv_std=pv_std, load_std=load_std
            ).iloc[t:]

            results_noisy = self.optimize_schedule(
                df=df_window_noisy,
                initial_soc_override=actual_soc,
                final_soc_min_kwh=self.battery["soc_initial_kwh"],
                printing=False,
            )
            planned_schedule = results_noisy["battery_schedule_kw"].iloc[0]

            real_pv = df_actual["pv_power_kw"].iloc[t]
            real_load = df_actual["fixed_demand_kw"].iloc[t]
            soc_at_start = actual_soc

            if planned_schedule >= 0:
                soc_change = planned_schedule * self.battery["eta_charge"] * 0.25
            else:
                soc_change = (planned_schedule / self.battery["eta_discharge"]) * 0.25

            # The plan respects the SOC limits, clipping only removes rounding errors
            actual_soc = np.clip(
                actual_soc + soc_change,
                self.battery["soc_min_kwh"],
                self.battery["soc_max_kwh"],
            )

            real_net_demand = real_load + planned_schedule - real_pv
            realized_results.append(
                {
                    "time": current_time,
                    "pv_power_kw": real_pv,
                    "fixed_demand_kw": real_load,
                    "battery_schedule_kw": planned_schedule,
                    "soc_kwh": soc_at_start,
                    "net_demand_kw_pos": max(0, real_net_demand),
                    "net_demand_kw_neg": max(0, -real_net_demand),
                    "demand_price_eur_per_kwh": df_actual[
                        "demand_price_eur_per_kwh"
                    ].iloc[t],
                    "supply_price_eur_per_kwh": df_actual[
                        "supply_price_eur_per_kwh"
                    ].iloc[t],
                }
            )

        return pd.DataFrame(realized_results).set_index("time"), actual_soc

    @staticmethod
    def calculate_scenario_costs(
        df_results: pd.DataFrame,
        demand_price: pd.Series,
        supply_price: pd.Series,
        timestep_hours: float = 0.25,
    ) -> float:
        df_results["cost_import_eur"] = (
            df_results["net_demand_kw_pos"] * timestep_hours * demand_price
        )
        df_results["revenue_export_eur"] = (
            df_results["net_demand_kw_neg"] * timestep_hours * supply_price
        )
        df_results["net_cost_eur"] = (
            df_results["cost_import_eur"] - df_results["revenue_export_eur"]
        )
        return df_results["net_cost_eur"].sum()

    @staticmethod
    def generate_uncertain_predictions(
        df: pd.DataFrame, pv_std: float = 0.10, load_std: float = 0.10
    ) -> pd.DataFrame:
        df_forecast = df.copy()
        pv_noise = np.random.normal(0, df["pv_power_kw"].max() * pv_std, len(df))
        noisy_pv = df["pv_power_kw"] + pv_noise
        df_forecast["pv_power_kw"] = np.where(
            df["pv_power_kw"] > 0, np.clip(noisy_pv, 0, None), 0.0
        )

        load_noise = np.random.normal(
            0, df["fixed_demand_kw"].max() * load_std, len(df)
        )
        df_forecast["fixed_demand_kw"] = np.clip(
            df["fixed_demand_kw"] + load_noise, 0, None
        )
        return df_forecast
