import os

DB_PATH = "chat_history.db"

if os.path.exists(DB_PATH):
    try:
        os.remove(DB_PATH)
        print("\n==================================================")
        print("¡ÉXITO! Base de datos de chats eliminada por completo.")
        print("Tu frontend y tu backend están 100% limpios para la demo.")
        print("==================================================\n")
    except Exception as e:
        print(f"Error al eliminar la base de datos (asegúrate de cerrar el servidor primero): {e}")
else:
    print("\nLa base de datos ya está limpia o no existe.\n")