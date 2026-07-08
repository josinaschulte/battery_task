Attached you will find a location_graph.png which is there to give you an impression on the setup of the test customer. The test customer provided PV and consumption data which we assume to be data that will be produced and consumed for the next day at the times (starting at the time in the same row and ending at the time of the next row) provided in the csvs. Additionally, the customer wants to see how a battery would perform in their setup.
Regarding the optimization, the test customer requested a one-day (period of 24h) optimization in 15 minute frequency. The objective is to make decisions for the battery to minimize energy cost. Further, the supply of energy to the grid is allowed, but to be miminized (more important than cost savings).
The desired outcome for the test customer is a schedule for the battery: how to operate the battery in a 15 minute frequency by charging > 0 and discharging < 0 to provide the best solution.
Please use Pyomo or oemof as an interface. Whatever you feel more comfortable with or what you want to test.

You may assume:
- perfect foresight for the provided data
- no battery degradation cost unless you want to add one
- battery cannot charge and discharge at the same time
- please pay attention to the input data format and units
- please document any further assumptions and preprocessing steps