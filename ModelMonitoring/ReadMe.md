# Model Monitoring with Label Studio! 
LabelStudio is about more than just handling your training data creation -- it can also be used to monitor 
your production  models for quality and drift. 

## How to use this package 
1. Download this repo to wherever you plan to run your code and cd into the folder
2. Create a new conda environment wherever you'll be running this code

`conda create --name ModelMonitoring python=3.10`

3. Install all necessary packages 

`pip install -r requirements.txt `

4. Fill out the `config.ini` file with all of your credentials as specified
5. In `Scrape_logs.py`, edit the logic to properly access your logs. You can follow the comments
in the file to properly build this out, but the important thing is that the `scrape()` method returns 
a list of dictionaries, where the keys map to your fields for data import as specified in your `labeling_config`
AND one of the fields is "date" if `sample_by_date` is TRUE in your config.ini 
6. Run `monitor_project_with_ls.py` as the main file. We reccomend doing this as a weekly chron job, 
so that you can constantly monitor your production projects! 