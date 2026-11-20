from dataclasses import dataclass, field
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

plt.style.use("latex_style.mplstyle")


@dataclass
class Plotter:
    timezone: str
    date: pd.Timestamp
    x_min: pd.Timestamp
    x_max: pd.Timestamp

    def plot_timeseries(
        self,
        plot_data: list[pd.Series],
        plot_label: list[str],
        colors: list[str],
        y_label: str,
        filename: str,
    ) -> None:
        plt.figure()
        plt.axhline(0, color="black", lw=0.6)

        for i, plot_df in enumerate(plot_data):
            plt.step(
                plot_df.index,
                plot_df,
                label=plot_label[i],
                where="post",
                color=colors[i],
            )

        plt.gca().xaxis.set_major_formatter(
            mdates.DateFormatter("%H:%M", tz=self.timezone)
        )
        plt.xlim(self.x_min, self.x_max)
        plt.xlabel(
            f"Time at {self.date.day}.{self.date.month}.{self.date.year} in {self.timezone} time"
        )
        plt.ylabel(y_label)
        plt.legend()
        plt.savefig(filename)
        plt.close()

    def plot_double_axis(
        self,
        left_data: list[pd.Series],
        left_label: list[str],
        left_color: str,
        right_data: list[pd.Series],
        right_label: list[str],
        right_color: str,
        left_ylabel: str,
        right_ylabel: str,
        filename: str,
    ) -> None:
        fig, ax1 = plt.subplots()

        linestyles = ["-", "--"]
        for i, series in enumerate(left_data):
            ax1.step(
                series.index,
                series,
                label=left_label[i],
                where="post",
                color=left_color,
                linestyle=linestyles[i % len(linestyles)],
            )

        ax1.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=self.timezone))
        ax1.set_xlim(self.x_min, self.x_max)
        ax1.set_xlabel(
            f"Time at {self.date.day}.{self.date.month}.{self.date.year} in {self.timezone} time"
        )
        ax1.set_ylabel(left_ylabel, color=left_color)
        ax1.tick_params(axis="y", labelcolor=left_color)

        ax2 = ax1.twinx()
        for i, series in enumerate(right_data):
            ax2.step(
                series.index,
                series,
                label=right_label[i],
                where="post",
                color=right_color,
                linestyle=linestyles[i % len(linestyles)],
            )

        ax2.set_ylabel(right_ylabel, color=right_color)
        ax2.tick_params(axis="y", labelcolor=right_color)

        ax1.grid(True)
        ax2.grid(False)

        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2)

        fig.tight_layout()
        fig.savefig(filename)
        plt.close(fig)

    def plot_energy_dashboard(
        self,
        # Panel 1: Power balance
        power_data: list[pd.Series],
        power_labels: list[str],
        power_colors: list[str],
        power_ylabel: str,
        # Panel 2: Battery (SOC & schedule)
        soc_data: pd.Series,
        soc_label: str,
        soc_color: str,
        soc_ylabel: str,
        schedule_data: pd.Series,
        schedule_label: str,
        schedule_color: str,
        schedule_ylabel: str,
        # Panel 3: Prices
        price_data: list[pd.Series],
        price_labels: list[str],
        price_colors: list[str],
        price_ylabel: str,
        filename: str,
        power_mins: list[pd.Series] = None,
        power_maxes: list[pd.Series] = None,
        power_linestyles: list[str] = None,
        power_alphas: list[float] = None,
        soc_min: pd.Series = None,
        soc_max: pd.Series = None,
        schedule_min: pd.Series = None,
        schedule_max: pd.Series = None,
    ) -> None:
        fig, (ax1, ax2, ax3) = plt.subplots(
            nrows=3, ncols=1, sharex=True, figsize=(8, 12)
        )

        if power_linestyles is None:
            power_linestyles = ["-"] * len(power_data)
        if power_alphas is None:
            power_alphas = [1.0] * len(power_data)

        # --- Panel 1: Power balance ---
        ax1.axhline(0, color="black", lw=0.6)
        for i, series in enumerate(power_data):
            if power_mins is not None and power_maxes is not None:
                ax1.fill_between(
                    series.index,
                    power_mins[i],
                    power_maxes[i],
                    step="post",
                    color=power_colors[i],
                    alpha=0.2,
                    lw=0,
                )
            ax1.step(
                series.index,
                series,
                label=power_labels[i],
                where="post",
                color=power_colors[i],
                linestyle=power_linestyles[i],
                alpha=power_alphas[i],
            )
        ax1.set_ylabel(power_ylabel)
        ax1.legend(loc="upper right")
        ax1.grid(True)

        # --- Panel 2: Battery ---
        ax2.axhline(0, color="black", lw=0.6)

        # SOC
        soc_display_label = f"{soc_label} (Mean)" if soc_min is not None else soc_label
        if soc_min is not None and soc_max is not None:
            ax2.fill_between(
                soc_data.index,
                soc_min,
                soc_max,
                step="post",
                color=soc_color,
                alpha=0.2,
                lw=0,
            )
        ax2.step(
            soc_data.index,
            soc_data,
            label=soc_display_label,
            where="post",
            color=soc_color,
        )
        ax2.set_ylabel(soc_ylabel, color=soc_color)
        ax2.tick_params(axis="y", labelcolor=soc_color)
        ax2.grid(True)

        # Schedule
        ax2_twin = ax2.twinx()
        schedule_display_label = (
            f"{schedule_label} (Mean)" if schedule_min is not None else schedule_label
        )
        if schedule_min is not None and schedule_max is not None:
            ax2_twin.fill_between(
                schedule_data.index,
                schedule_min,
                schedule_max,
                step="post",
                color=schedule_color,
                alpha=0.2,
                lw=0,
            )
        ax2_twin.step(
            schedule_data.index,
            schedule_data,
            label=schedule_display_label,
            where="post",
            color=schedule_color,
            linestyle="--",
        )
        ax2_twin.set_ylabel(schedule_ylabel, color=schedule_color)
        ax2_twin.tick_params(axis="y", labelcolor=schedule_color)
        ax2_twin.grid(False)

        lines2, labels2 = ax2.get_legend_handles_labels()
        lines2_twin, labels2_twin = ax2_twin.get_legend_handles_labels()
        ax2.legend(lines2 + lines2_twin, labels2 + labels2_twin, loc="upper right")

        # --- Panel 3: Prices ---
        for i, series in enumerate(price_data):
            ax3.step(
                series.index,
                series,
                label=price_labels[i],
                where="post",
                color=price_colors[i],
            )
        ax3.set_ylabel(price_ylabel)
        ax3.legend(loc="upper right")
        ax3.grid(True)

        ax3.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=self.timezone))
        ax3.set_xlim(self.x_min, self.x_max)
        ax3.set_xlabel(
            f"Time at {self.date.day}.{self.date.month}.{self.date.year} in {self.timezone} time"
        )

        fig.subplots_adjust(hspace=0.05)
        fig.savefig(filename)
        plt.close(fig)

    def plot_cost_distribution(
        self, costs: list[float], reference_cost: float, filename: str
    ) -> None:
        plt.figure(figsize=(8, 5))

        plt.hist(
            costs,
            bins=10,
            color="darkgrey",
            edgecolor="black",
            alpha=0.7,
            label="Monte-Carlo Szenarien",
        )

        # Reference: perfect foresight model
        plt.axvline(
            reference_cost,
            color="black",
            linestyle="-",
            linewidth=2,
            label=f"Perfect foresight ({reference_cost:.2f} €)",
        )
        # Mean cost
        mean_cost = np.mean(costs)
        plt.axvline(
            mean_cost,
            color="dimgrey",
            linestyle="--",
            linewidth=2,
            label=f"Expected cost (mean: {mean_cost:.2f} €)",
        )

        plt.xlabel("Total daily cost / €")
        plt.ylabel("Number of scenarios")
        plt.legend()
        plt.grid(axis="y", alpha=0.3)

        plt.tight_layout()
        plt.savefig(filename)
        plt.close()


@dataclass
class EnergyPlotter(Plotter):
    assume_mislabel: bool = False
    colors: dict = field(init=False)

    def __post_init__(self):
        """Initialize standard color palette for all energy plots."""
        c = plt.rcParams["axes.prop_cycle"].by_key()["color"]
        self.colors = {
            "consumption": c[0],
            "pv": c[1],
            "demand": c[2],
            "battery": c[3],
            "import": "dimgrey",
            "export": "darkgrey",
        }

    def _get_filename(self, prefix: str) -> str:
        """Generate standardized filenames based on arguments."""
        suffix = "_mislabel" if self.assume_mislabel else ""
        return f"plots/{prefix}_{self.timezone[:3]}{suffix}.png"

    def plot_scenario_1(
        self, df_raw: pd.DataFrame, df_pre: pd.DataFrame, total_price: float
    ):
        """Overview of the test customer without battery."""

        # PV and Consumption
        self.plot_timeseries(
            [
                df_raw["pv_power_kw"],
                df_raw["fixed_demand_kw"],
            ],
            ["PV", "Consumption"],
            [self.colors["pv"], self.colors["consumption"]],
            "Power / kW",
            self._get_filename("1_pv_cons_raw"),
        )

        # Prices
        self.plot_timeseries(
            [df_pre["supply_price_eur_per_kwh"], df_pre["demand_price_eur_per_kwh"]],
            ["Supply", "Demand"],
            [self.colors["export"], self.colors["import"]],
            "Grid price / (€ / kWh)",
            self._get_filename("1_price"),
        )

        # Net Demand
        self.plot_timeseries(
            [df_pre["fixed_demand_kw"], df_pre["pv_power_kw"], df_pre["net_demand_kw"]],
            ["Consumption", "PV", "Net demand"],
            [self.colors["consumption"], self.colors["pv"], self.colors["demand"]],
            "Power / kW",
            self._get_filename("1_net_demand"),
        )

        # Power demand & price
        self.plot_double_axis(
            [df_pre["net_demand_kw"]],
            ["Power demand"],
            self.colors["demand"],
            [df_pre["demand_price_eur_per_kwh"], df_pre["supply_price_eur_per_kwh"]],
            ["Demand price", "Supply price"],
            self.colors["export"],
            "Net power demand / kW",
            "Grid price / (€ / kWh)",
            self._get_filename("1_demand_price"),
        )

        # Net cost
        self.plot_timeseries(
            [df_pre["price_eur"]],
            [f"Net cost per 15min, Total: {total_price:.2f} €"],
            [self.colors["export"]],
            "Cost / €",
            self._get_filename("1_net_cost"),
        )

    def plot_scenario_2(
        self, df_pre: pd.DataFrame, results_df: pd.DataFrame, total_cost: float
    ):
        """Optimized battery schedule."""
        self.plot_double_axis(
            [results_df["soc_kwh"]],
            ["Battery SOC"],
            self.colors["battery"],
            [results_df["battery_schedule_kw"]],
            ["Battery schedule"],
            self.colors["export"],
            "Battery state of charge / kWh",
            "Battery schedule / kW (charge > 0, discharge < 0)",
            self._get_filename("2_optimized_battery_soc"),
        )

        self.plot_energy_dashboard(
            power_data=[
                df_pre["pv_power_kw"],
                df_pre["fixed_demand_kw"],
                results_df["net_demand_kw_pos"],
            ],
            power_labels=["PV Generation", "Consumption", "Grid Import"],
            power_colors=[
                self.colors["pv"],
                self.colors["consumption"],
                self.colors["import"],
            ],
            power_ylabel="Power / kW",
            soc_data=results_df["soc_kwh"],
            soc_label="Battery SOC",
            soc_color=self.colors["battery"],
            soc_ylabel="SOC / kWh",
            schedule_data=results_df["battery_schedule_kw"],
            schedule_label="Battery Schedule \n" + r"(Charge$>0$, Discharge$<0$)",
            schedule_color=self.colors["import"],
            schedule_ylabel="Schedule / kW",
            price_data=[
                df_pre["demand_price_eur_per_kwh"],
                df_pre["supply_price_eur_per_kwh"],
            ],
            price_labels=["Grid Demand Price (Import)", "Grid Supply Price (Export)"],
            price_colors=[self.colors["import"], self.colors["export"]],
            price_ylabel="Price / (€/kWh)",
            filename=self._get_filename("2_energy_dashboard"),
        )

        self.plot_timeseries(
            [results_df["net_cost_eur"]],
            [f"Optimized net cost per 15min, Total: {total_cost:.2f} €"],
            [self.colors["export"]],
            "Cost / €",
            self._get_filename("2_optimized_net_cost"),
        )

    def plot_scenario_3(self, df_pre: pd.DataFrame, stats: dict):
        """Monte Carlo Sensitivity variance."""
        self.plot_energy_dashboard(
            power_data=[stats["pv_mean"], stats["load_mean"], stats["import_mean"]],
            power_labels=["PV Generation", "Consumption", "Grid Import"],
            power_colors=[
                self.colors["pv"],
                self.colors["consumption"],
                self.colors["import"],
            ],
            power_ylabel="Power / kW",
            soc_data=stats["soc_mean"],
            soc_label="Battery SOC",
            soc_color=self.colors["battery"],
            soc_ylabel="SOC / kWh",
            schedule_data=stats["schedule_mean"],
            schedule_label="Battery Schedule \n" + r"(Charge$>0$, Discharge$<0$)",
            schedule_color=self.colors["export"],
            schedule_ylabel="Schedule / kW",
            price_data=[
                df_pre["demand_price_eur_per_kwh"],
                df_pre["supply_price_eur_per_kwh"],
            ],
            price_labels=["Grid Demand Price", "Grid Supply Price"],
            price_colors=[self.colors["export"], self.colors["import"]],
            price_ylabel="Price / (€/kWh)",
            filename=self._get_filename("3_energy_dashboard_mc_variance"),
            power_mins=[stats["pv_min"], stats["load_min"], stats["import_min"]],
            power_maxes=[stats["pv_max"], stats["load_max"], stats["import_max"]],
            soc_min=stats["soc_min"],
            soc_max=stats["soc_max"],
            schedule_min=stats["schedule_min"],
            schedule_max=stats["schedule_max"],
        )

    def plot_scenario_4(self, results_df_mpc: pd.DataFrame):
        """Model Predictive Control results with the actual PV and consumption."""
        self.plot_energy_dashboard(
            power_data=[
                results_df_mpc["pv_power_kw"],
                results_df_mpc["fixed_demand_kw"],
                results_df_mpc["net_demand_kw_pos"],
                results_df_mpc["net_demand_kw_neg"],
            ],
            power_labels=[
                "PV Generation",
                "Consumption",
                "Grid Import",
                "Grid Supply (Export)",
            ],
            power_colors=[
                self.colors["pv"],
                self.colors["consumption"],
                self.colors["import"],
                self.colors["export"],
            ],
            power_ylabel="Power / kW",
            soc_data=results_df_mpc["soc_kwh"],
            soc_label="Battery SOC",
            soc_color=self.colors["battery"],
            soc_ylabel="SOC / kWh",
            schedule_data=results_df_mpc["battery_schedule_kw"],
            schedule_label="Battery Schedule \n" + r"(Charge$>0$, Discharge$<0$)",
            schedule_color=self.colors["export"],
            schedule_ylabel="Schedule / kW",
            price_data=[
                results_df_mpc["demand_price_eur_per_kwh"],
                results_df_mpc["supply_price_eur_per_kwh"],
            ],
            price_labels=["Grid Demand Price", "Grid Supply Price"],
            price_colors=[self.colors["import"], self.colors["export"]],
            price_ylabel="Price / (€/kWh)",
            filename=self._get_filename("4_energy_dashboard_mpc"),
        )
