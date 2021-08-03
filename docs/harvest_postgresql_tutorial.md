# Harvest with PostgreSQL

## Installation and Setup:

### Harvest

```bash
pip install -e 'git+https://github.com/tfukaza/harvest.git#egg=harvest'
```

### SQLAlchemy

```bash
pip install SQLAlchemy
pip install pg8000 # Connects SQLAlchemy to the PostgreSQL database
```

### PostgreSQL

See PostgreSQL installation guide [here](https://www.postgresql.org/download/)

Now create a user with a password and give it access to the default postgres database.

```bash
sudo -u postgres -i
psql 
CREATE SCHEMA harvest;
CREATE USER username PASSWORD 'password';
GRANT ALL ON SCHEMA harvest TO username;
GRANT ALL ON ALL TABLES IN SCHEMA harvest TO username;
GRANT ALL PRIVILEGES ON DATABASE postgres TO username;
\q
```

## Implementation:

```python
from harvest.storage.database_storage import DBStorage
from harvest.algo import BaseAlgo
from harvest.trader import Trader

# The formatting here is dialect+driver://username:password@host:port/database
postgre_storage = DBStorage('postgresql+pg8000://username:password@localhost/postgres')

class Watch(BaseAlgo):
    def main(self, meta):
        print( self.get_asset_price() )

if __name__ == "__main__":
    t = Trader(storage=postgre_storage)
    t.set_symbol('AAPL')
    t.set_algo(Watch())

    t.start('1MIN')
```

 While this runs, checkout the entries in the database.

 ```bash
 psql -U user -d postgres
 \dt # shows tables
 select * from asset;
 ```
