import psycopg2

DATABASE_URL = "postgresql://username:password@db:5432/database_name"  # Replace this with your actual database URL

# Connect to the PostgreSQL database
connection = psycopg2.connect(DATABASE_URL)
cursor = connection.cursor()

# Check the table schema
cursor.execute(
    "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'transcriptions';"
)
print("Table schema:")
for column in cursor.fetchall():
    print(column)

# Drop the table
cursor.execute("DROP TABLE IF EXISTS transcriptions;")
connection.commit()
print("Table 'transcriptions' dropped.")

# Close the database connection
cursor.close()
connection.close()
