from pandas.core.indexes.datetimes import DatetimeIndex
from pandas.core.frame import DataFrame
import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Union
from pandas._libs.tslibs.nattype import NaTType


@dataclass
class Test_Customer_Data:
    """
    Configuration and preprocessing pipeline for consumption, PV, and grid data.
    Standard units: kW, kWh, 15 minute time intervals
    """

    consumption_file_path: str
    pv_file_path: str
    target_timezone: str
    grid_dict: dict[str, list[float] | float]
    grid_start_date: Union[pd.Timestamp, NaTType]
    assume_mislabel: bool = False

    def get_consumption_data(self) -> pd.DataFrame:
        """
        Imports the consumption data and converts it to 15 minute frequency data
        in the target time zone.
        If assume_mislabel is True, the Europe/Berlin local time zone label is assumed to be incorrect
        and the data is assumed to be in UTC despite the label.
        """
        consumption_data: DataFrame = pd.read_csv(
            filepath_or_buffer=self.consumption_file_path,
            parse_dates=["timestamp [Europe/Berlin local]"],
            dayfirst=True,
            index_col="timestamp [Europe/Berlin local]",
        )

        # Convert unit from W to kW and remove unnecessary columns
        consumption_data["fixed_demand_kw"] = consumption_data["fixed_demand_w"] / 1e3
        consumption_data = consumption_data[["fixed_demand_kw"]]

        # Convert to 15 minute intervals by forward filling the values
        complete_index = pd.date_range(
            start=consumption_data.index.min(),
            end=consumption_data.index.max() + pd.Timedelta(minutes=45),
            freq="15min",
        )

        consumption_data = consumption_data.reindex(complete_index).ffill()

        consumption_data.index = consumption_data.index.tz_localize("Europe/Berlin")
        if self.target_timezone != "Europe/Berlin":
            consumption_data.index = consumption_data.index.tz_convert(
                self.target_timezone
            )

        # rename for consistency
        consumption_data.index.names = ["timestamp"]
        return consumption_data

    def get_pv_data(self) -> pd.DataFrame:
        """
        Imports PV data and converts it to chosen target_timezone.
        """
        pv_data: DataFrame = pd.read_csv(
            filepath_or_buffer=self.pv_file_path,
            parse_dates=["timestamp [UTC]"],
            index_col="timestamp [UTC]",
        )

        if self.target_timezone != "UTC":
            pv_data.index = pv_data.index.tz_convert(self.target_timezone)  # ty:ignore[unresolved-attribute]

        # rename for consistency
        pv_data.index.names = ["timestamp"]
        return pv_data

    def get_grid_price_data(self) -> pd.DataFrame:
        """
        Generates pd.DataFrame from grid dict with variable start date based on assumed time zone of data,
        upsamples it to 15 minute intervals
        and converts it to target time zone as well.
        """
        grid_price: DataFrame = pd.DataFrame(
            {"demand_price_eur_per_kwh": self.grid_dict["demand_price_eur_per_kwh"]},
            index=pd.date_range(start=self.grid_start_date, periods=24, freq="h"),
        )

        # Convert to 15 minute intervals by forward filling the values
        complete_index: DatetimeIndex = pd.date_range(
            start=grid_price.index.min(),
            end=grid_price.index.max() + pd.Timedelta(minutes=45),
            freq="15min",
        )

        grid_price = grid_price.reindex(complete_index).ffill()

        # Add supply price as a constant column
        grid_price["supply_price_eur_per_kwh"] = self.grid_dict[
            "supply_price_eur_per_kwh"
        ]

        grid_price.index = grid_price.index.tz_convert(self.target_timezone)  # ty:ignore[unresolved-attribute]

        # rename for consistency
        grid_price.index.names = ["timestamp"]
        return grid_price

    def preprocess_data(self) -> pd.DataFrame:
        """
        Retrieves and merges consumption, PV, and grid price datasets on their timezone-aligned index.
        Adds net demand column by subtracting PV power from consumption.

        Preprocesses PV and consumption data based on assume_mislabel
        if assume_mislabel:
            the timezone of the consumption data is reset to UTC thus ensuring 24 overlap
            of PV and consumption data
        else:
            the PV data is extended with 0s for the 2h during the night due
            to no expected PV power generation during the night ensuring 24h overlap

        column names in output DataFrame:
            consumption: "fixed_demand_kw"
            pv: "pv_power_kw"
            demand: "net_demand_kw", "net_demand_kw_pos", "net_demand_kw_neg"
            grid: "demand_price_eur_per_kwh", "supply_price_eur_per_kwh"
            price: "price_eur"
        """
        consumption: DataFrame = self.get_consumption_data()
        pv: DataFrame = self.get_pv_data()
        grid: DataFrame = self.get_grid_price_data()

        if self.assume_mislabel:
            # Force UTC as original time zone when assuming mislabeled timestamp column
            consumption.index = consumption.index.tz_localize(None).tz_localize("UTC")
            grid.index = grid.index.tz_localize(None).tz_localize("UTC")
            if self.target_timezone != "UTC":
                consumption.index = consumption.index.tz_convert(self.target_timezone)
                grid.index = grid.index.tz_convert(self.target_timezone)
        else:
            # Extend PV data back to midnight Europe/Berlin local time with 0s
            pv = pv.reindex(consumption.index).fillna(0)

        demand: DataFrame = pd.DataFrame(
            {"net_demand_kw": consumption["fixed_demand_kw"] - pv["pv_power_kw"]}
        )

        # Split net demand into positive and negative tracks
        demand["net_demand_kw_pos"] = np.where(
            demand["net_demand_kw"] >= 0, demand["net_demand_kw"], np.nan
        )
        demand["net_demand_kw_neg"] = np.where(
            demand["net_demand_kw"] < 0, demand["net_demand_kw"], np.nan
        )

        # Calculate cost and revenue. Factor 0.25 for power to energy conversion (15min = 0.25h time intervals)
        cost = demand["net_demand_kw_pos"] * 0.25 * grid["demand_price_eur_per_kwh"]
        revenue = demand["net_demand_kw_neg"] * 0.25 * grid["supply_price_eur_per_kwh"]

        price: pd.DataFrame = pd.DataFrame(
            {"price_eur": cost.add(revenue, fill_value=0)}
        )

        # Outer join all three DataFrames
        combined_data = consumption.join([pv, demand, grid, price], how="outer")
        return combined_data
