import sqlite3
from sqlite3 import Error

from lib.Logger import *

class Database:

    def __init__(self, db_name="bot.db"):
        self.name = db_name
        self.conn = self.connect(db_name)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def connect(self, db_name):
        try:
            return sqlite3.connect(db_name, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
        except Error as e:
            logger.error(e)
            pass

    def create_tables(self):

        try:
            self.cursor.execute("CREATE TABLE IF NOT EXISTS active_rooms \
                (id INTEGER PRIMARY KEY AUTOINCREMENT, \
                room_id INTEGER NOT NULL, \
                member_id INTEGER NOT NULL, \
                is_open INTEGER NOT NULL DEFAULT 0)")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS active_invitations \
                (id INTEGER PRIMARY KEY AUTOINCREMENT, \
                room_id INTEGER NOT NULL, \
                member_id INTEGER NOT NULL)")

        except Error as e:
            logger.error(e)
            return False

        self.conn.commit()
        return True

# GENERIC FUNCTIONS

    def execute_statement(self, statement):

        try:
            self.cursor.execute(statement)
        except Error as e:
            logger.error(e)
            return False
        return True

    def get_value(self, member_id, table, attribute):

        if self.member_exists(member_id):

            statement = f"SELECT {attribute} FROM {table} WHERE member_id = {int(member_id)}"

            if self.execute_statement(statement):

                result = self.cursor.fetchall()
                return result[0][0]
            
            return 0
        
        return 0

# PRIVATE ROOMS

    def invite_member(self, room_id, member_id):

        statement = f"INSERT INTO active_invitations (room_id, member_id) VALUES ({int(room_id)}, {int(member_id)})"
        if self.execute_statement(statement):
            self.conn.commit()
            return True
        return False

    def uninvite_member(self, room_id, member_id):
        statement = f"DELETE FROM active_invitations WHERE member_id = {int(member_id)} AND room_id = {int(room_id)}"
        if self.execute_statement(statement):
            self.conn.commit()
            return True
        return False

    def get_all_invited_members(self, room_id):
        statement = f"SELECT * FROM active_invitations WHERE room_id = {int(room_id)}"
        if self.execute_statement(statement):
            result = self.cursor.fetchall()
            if result:
                return result
        return False

    def is_member_invited(self, room_id, member_id):
        statement = f"SELECT EXISTS (SELECT 1 FROM active_invitations WHERE member_id = {int(member_id)} AND room_id = {int(room_id)} LIMIT 1)"
        if self.execute_statement(statement):
            result = self.cursor.fetchall()
            if result[0][0]:
                return True
        return False

    def add_private_room(self, room_id, member_id):
        statement = f"INSERT INTO active_rooms (room_id, member_id) VALUES ({int(room_id)}, {int(member_id)})"
        if self.execute_statement(statement):
            self.conn.commit()
            return True
        return False

    def is_room_private(self, room_id):
        statement = f"SELECT EXISTS (SELECT 1 FROM active_rooms WHERE room_id = {int(room_id)} LIMIT 1)"
        if self.execute_statement(statement):
            result = self.cursor.fetchall()
            if result[0][0]:
                return True
        return False
    
    def is_owner(self, room_id, member_id):
        statement = f"SELECT EXISTS (SELECT 1 FROM active_rooms WHERE room_id = {int(room_id)} AND member_id = {int(member_id)} LIMIT 1)"
        if self.execute_statement(statement):
            result = self.cursor.fetchall()
            if result[0][0]:
                return True
        return False

    def is_already_owner(self, member_id):
        statement = f"SELECT EXISTS (SELECT 1 FROM active_rooms WHERE member_id = {int(member_id)} LIMIT 1)"
        if self.execute_statement(statement):
            result = self.cursor.fetchall()
            if result[0][0]:
                return True
        return False

    def get_owner_room(self, member_id):
        statement = f"SELECT room_id FROM active_rooms WHERE member_id = {int(member_id)}"
        if self.execute_statement(statement):
            result = self.cursor.fetchall()
            if result:
                return result[0][0]
        return False

    def is_open(self, room_id):
        statement = f"SELECT is_open FROM active_rooms WHERE room_id = {int(room_id)}"
        if self.execute_statement(statement):
            result = self.cursor.fetchall()
            if result and result[0][0]:
                return True
        return False

    def open_room(self, room_id):
        statement = f"UPDATE active_rooms SET is_open = 1 WHERE room_id = {int(room_id)}"
        if self.execute_statement(statement):
            self.conn.commit()
            return True
        return False
    
    def close_room(self, room_id):
        statement = f"UPDATE active_rooms SET is_open = 0 WHERE room_id = {int(room_id)}"
        if self.execute_statement(statement):
            self.conn.commit()
            return True
        return False
        
    def delete_private_room(self, room_id):
        statement = f"DELETE FROM active_rooms WHERE room_id = {int(room_id)}"
        if self.execute_statement(statement):
            statement = f"DELETE FROM active_invitations WHERE room_id = {int(room_id)}"
            if self.execute_statement(statement):
                self.conn.commit()
                return True
        return False

    def transfer_ownership(self, from_id, to_id):
        statement = f"UPDATE active_rooms SET member_id = {int(to_id)} WHERE member_id = {int(from_id)}"
        if self.execute_statement(statement):
            self.conn.commit()
            return True
        return False