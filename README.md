# Bulk add to Trail Reservation Py Utility

> Written by Owen Ling 18/07/25  
> Located in Scripting & Automation/ROH/Trail  
> Version B.1

A simple Python utility to automate the UI process for adding multiple assets to a Trail.fi reservation, using the
Selenium web UI automation framework, written for the ROH.

## Environment Setup

Clone the repository
```cmd
git clone https://github.com/OLI6532/Trail-Reservations-Bulk-Add
```

Create a dedicated automated user in Trail with the minimum required privileges for the task and ass their login details
to a `.env` file as below, located in the same directory as the `bulk_add_to_reservation.py` file.

```dotenv
TRAIL_USERNAME=example@example.com
TRAIL_PASSWORD=foobar1234
```

## Using the utility
- Configure and activate the Python virtual environment:
```cmd
cd Trail-Reservations-Bulk-Add
python -m venv .venv
source .venv/bin/activate
```

- `(.venv)` should now be shown at the start of the terminal prompt, e.g.;

```cmd
(.venv) wing2 OLI-M-2 ~/Trail-Reservations $ 
```

> [!NOTE]
> To exit the virtual environment, enter `deactivate`

- Install the project requirements:

```cmd
pip install -r requirements.txt 
```

- Define a list of barcodes in a `.CSV` file that you want to add to the reservation
- Identify the reservation ID found in the URL when opened in Trail
- Run the script
  ```cmd
  python reservation_bulk_add.py -R <reservation_id> -C <path_to_csv_file> -S <site_url> --headless
  ```

## Command Line Switches

- `-R` The ID of the reservation to add barcodes to
- `-C` Path to the CSV file containing the list of barcodes to add
- `-S` The Trail Site URL to use for the session. e.g.; `foo.trail.fi`
- `-T` Number of threads to use for concurrent browser sessions (Default: 3)
- `-H` Runs in headless mode, doesn't show the browser window (Optional)
- `-U` The username to log in with (Optional)
- `-P` The password of the username to log in with (Optional)
- `-Q` Suppresses all STDOUT messages, except for errors
- `-h` Show help 
