from pathlib import Path
from datetime import date, datetime

class PathManager:
    def __init__(self, base_dir: Path, animal_id: str):
        """
        Initialize with a base directory and task type.
        Parameters:
            base_dir (Path): The base directory where data for animals/tasks is stored.
            task_type (str): The type of task for this handler.
        """
        self.base_dir = base_dir
        self.animal_id = animal_id

    def check_dir(self):
        """
        Function to check if directory for storing animal data exists, and create if it doesn't
        :return: animal_dir: Path
        """

        data_directory = self.base_dir.joinpath('data')
        animal_dir = data_directory.joinpath(self.animal_id)
        if animal_dir.exists():
            pass
        else:
            animal_dir.mkdir()
        return animal_dir

    def make_exp_dir(self):
        """
        Create directory to store experimental data

        :param animal_dir: Path
        :return: exp_dir: Path
        """
        animal_dir = self.check_dir()
        date_dir = animal_dir.joinpath(self.get_today())  # store data in folders per day
        exp_dir = date_dir.joinpath(self.get_hours())
        exp_dir.mkdir(parents=True)

        return exp_dir

    def get_today(self):
        """
        Dummy function to get date in YYYYMMDD format
        :return: today: str
        """
        datetime_format = '%Y%m%d'
        today = date.today().strftime(datetime_format)
        return today

    def get_hours(self):
        """
        Dummy function to get current timestamp in HHMMSS format
        :return: hrs: str
        """
        hour_format = "%H%M%S"
        now = datetime.now()
        hrs = now.strftime(hour_format)
        return hrs