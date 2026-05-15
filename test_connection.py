import os
NEO4J_USERNAME = "d0bb7655"
NEO4J_PASSWORD = "ItJGkE4mTbyLWVk1SNwOte-7rf5EKHZsWkY8xE4C8is"
NEO4J_URI = "neo4j+ssc://d0bb7655.databases.neo4j.io"

from neo4j import GraphDatabase
uri = NEO4J_URI
username = NEO4J_USERNAME
password = NEO4J_PASSWORD
driver = GraphDatabase.driver(uri, auth=(username, password))
try:
   driver.verify_connectivity()
   print("Connection successful!")
except Exception as e:
   print(f"Failed to connect to Neo4j: {e}")

driver.close()