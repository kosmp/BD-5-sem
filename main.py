import psycopg2
import re
import getpass
from datetime import datetime

conn = psycopg2.connect(
    host="localhost",
    port="5432",
    database="fruit_shop",
    user="kosmp",
    password="123456",
)

logged_in = False

def is_valid_phone(phone):
    return re.match(r'\+375[0-9]{9}', phone) is not None

def is_valid_password(password):
    return len(re.findall(r'\d', password)) >= 4

def select_fruits():
    with conn.cursor() as cursor:
        cursor.execute("SELECT Name, Price FROM fruits;")
        rows = cursor.fetchall()
        print("\nСписок фруктов:")
        print("Наименование          | Цена")
        print("----------------------|------")
        for row in rows:
            print(f"{row[0]:22} | {row[1]:>5}")

def get_fruit_info(conn, fruit_name):
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT fruits.Id, fruits.Name, fruits.Creation_date, fruits.Price, 
                   fruits.Expiration_date, producers.Name AS Producer_Name, producers.Country
            FROM fruits
            JOIN producers ON fruits.Producer_Id = producers.Id
            WHERE fruits.Name = %s""", (f'{fruit_name}',))

        fruit = cursor.fetchone()

        if fruit:
            print("\nИнформация о фрукте:")
            print("ID              : ", fruit[0])
            print("Наименование    : ", fruit[1])
            print("Дата создания   : ", fruit[2])
            print("Цена            : ", fruit[3])
            print("Срок годности   : ", fruit[4])
            print("Производитель   : ", f"{fruit[5]} ({fruit[6]})\n")
            return True
        else:
            print(f"Фрукт с именем '{fruit_name}' не найден.\n")
            return False
            
def get_reviews_for_fruit(fruit_name):
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT Reviews.Id, Reviews.review_text, Reviews.evaluation, Users.First_Name, Users.Last_Name
            FROM Reviews
            JOIN Fruits ON Reviews.Fruit_Id = Fruits.Id
            JOIN Clients ON Reviews.Client_Id = Clients.Id
            JOIN Users ON Clients.User_Id = Users.Id
            WHERE LOWER(Fruits.Name) = LOWER(%s);
        """, (fruit_name,))

        reviews = cursor.fetchall()

        if reviews:
            print(f"\nОтзывы о фрукте '{fruit_name}':")
            print("ID | Текст отзыва                             | Оценка | Клиент ")
            print("----------------------------------------------------------------")
            for review in reviews:
                print(f"{review[0]:2} | {review[1]:40} | {review[2]:^6} | {review[3]:^6} {review[4]:^6}")
        else:
            print(f"Отзывов о фрукте '{fruit_name}' не найдено.")

def view_employees():
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT Employees.Id, Users.First_Name, Users.Last_Name, Employees.Salary, 
                   Work_time.start_work, Work_time.end_work, 
                   array_to_string(ARRAY_AGG(Positions.Name), ', ') as Positions
            FROM Employees
            JOIN Users ON Employees.User_Id = Users.Id
            JOIN Work_time ON Employees.Work_time_Id = Work_time.Id
            JOIN Positions_Employees ON Employees.Id = Positions_Employees.Employee_Id
            JOIN Positions ON Positions_Employees.Position_Id = Positions.Id
            GROUP BY Employees.Id, Users.First_Name, Users.Last_Name, Employees.Salary, 
                     Work_time.start_work, Work_time.end_work;
        """)

        employees = cursor.fetchall()

        if employees:
            print("\nИнформация о сотрудниках:")
            print("ID | Имя | Фамилия | Зарплата | Начало работы | Конец работы | Должности")
            print("------------------------------------------------------------------------")
            for employee in employees:
                print(f"{employee[0]:2} | {employee[1]} | {employee[2]} | {employee[3]} | {employee[4]} | {employee[5]} | {employee[6]}")
        else:
            print("Сотрудники не найдены.")

def get_client_id_by_user_id(conn, user_id):
    with conn.cursor() as cursor:
        cursor.execute("SELECT Id FROM Clients WHERE User_Id = %s", (user_id,))
        client_id = cursor.fetchone()
        return client_id[0] if client_id else None

def leave_review(conn, fruit_name):
    global logged_in
    global current_user_id

    if not logged_in:
        print("Для оставления отзыва необходимо войти в систему.")
        return
    
    if not is_client(conn, current_user_id):
        print("Только клиенты могут оставлять отзыв.")
        return
    
    client_id = get_client_id_by_user_id(conn, current_user_id)
    review_text = input("Введите текст отзыва: ")
    evaluation = int(input("Введите оценку (от 1 до 5): "))

    with conn.cursor() as cursor:
        cursor.execute("SELECT Id FROM Fruits WHERE LOWER(Name) = LOWER(%s);", (fruit_name,))
        fruit_id = cursor.fetchone()

        if not fruit_id:
            print(f"Фрукт с наименованием '{fruit_name}' не найден.")
            return

        try:
            cursor.execute("CALL AddReview(%s, %s, %s, %s)", 
                           (review_text, evaluation, client_id, fruit_id[0]))
            conn.commit()
            print("Отзыв успешно оставлен!")
        except Exception as e:
            conn.rollback()
            print(f"Ошибка при оставлении отзыва: {e}")

def make_order(conn, fruit_name):
    global logged_in
    global current_user_id

    if not logged_in:
        print("Для оформления заказа необходимо войти в систему.")
        return
    
    if not is_client(conn, current_user_id):
        print("Только клиенты могут совершать заказ.")
        return
    
    quantity = int(input("Введите количество фруктов для заказа: "))
    client_id = get_client_id_by_user_id(conn, current_user_id)
    with conn.cursor() as cursor:
        try:
            cursor.execute("SELECT Id, Price FROM Fruits WHERE LOWER(Name) = LOWER(%s);", (fruit_name,))
            fruit = cursor.fetchone()

            if not fruit:
                raise ValueError("Фрукт не найден.")
            
            total_price = fruit[1] * quantity

            creation_date = datetime.now().date()

            cursor.execute("""
                INSERT INTO Orders (Creation_date, Total_price, Item_quantity, Client_Id, Fruit_Id)
                VALUES (%s, %s, %s, %s, %s)
            """, (creation_date, total_price, quantity, client_id, fruit[0]))

            conn.commit()
            print("Заказ успешно совершен!")
        except Exception as e:
            conn.rollback()
            print(f"Ошибка при совершении заказа: {e}")

def show_history(conn):
    global logged_in
    global current_user_id

    if not logged_in:
        print("Для просмотра истории заказов необходимо войти в систему.")
        return
    
    client_id = get_client_id_by_user_id(conn, current_user_id)
    with conn.cursor() as cursor:
        try:
            cursor.execute("""
                SELECT O.Creation_date, D.Delivery_date, F.Name, O.Total_price, O.Item_quantity
                FROM Orders O
                LEFT JOIN Delivery D ON O.Id = D.Order_Id
                JOIN Fruits F ON O.Fruit_Id = F.Id
                WHERE O.Client_Id = %s
                ORDER BY O.Creation_date DESC;
            """, (client_id,))

            orders = cursor.fetchall()

            if not orders:
                print("У вас нет заказов.")
            else:
                print("\nИстория ваших заказов:")
                print("Дата создания | Дата доставки | Наименование фрукта | Общая стоимость | Количество | Статус")
                print("--------------------------------------------------------------------------------------------")
                for order in orders:
                    creation_date = order[0]
                    delivery_date = order[1]
                    fruit_name = order[2]
                    total_price = order[3]
                    item_quantity = order[4]

                    status = "Ожидается"
                    if delivery_date:
                        days_remaining = (delivery_date - datetime.now()).days
                        if days_remaining < 0:
                            status = "Доставлен"
                        elif days_remaining == 0:
                            status = "Доставка сегодня"
                        else:
                            status = f"Осталось {days_remaining} дней"

                    print(f"{creation_date} | {delivery_date} | {fruit_name} | {total_price} | {item_quantity} | {status}")
        except Exception as e:
            print(f"Ошибка при получении истории заказов: {e}")

def is_admin(conn, user_id):
    with conn.cursor() as cursor:
        cursor.execute("SELECT Role_Id FROM Users WHERE Id = %s", (user_id,))
        role_id = cursor.fetchone()
        return role_id and role_id[0] == 1 

def is_client(conn, user_id):
    with conn.cursor() as cursor:
        cursor.execute("SELECT Role_Id FROM Users WHERE Id = %s", (user_id,))
        role_id = cursor.fetchone()
        return role_id and role_id[0] == 2 

def is_employee(conn, user_id):
    with conn.cursor() as cursor:
        cursor.execute("SELECT Role_Id FROM Users WHERE Id = %s", (user_id,))
        role_id = cursor.fetchone()
        return role_id and role_id[0] == 3

def delete_client(conn, user_id):
    with conn.cursor() as cursor:
        try:
            cursor.execute("DELETE FROM Clients WHERE User_Id = %s", (user_id,))
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"Ошибка при удалении пользователя из таблицы клиентов: {e}")

def get_user_id_by_name(conn, user_name):
    with conn.cursor() as cursor:
        cursor.execute("SELECT Id FROM Users WHERE First_Name ILIKE %s", (user_name,))
        user_id = cursor.fetchone()
        return user_id[0] if user_id else None

def select_work_time():
    print("Выберите вариант времени работы:")
    print("1. 00:00 - 08:00")
    print("2. 08:00 - 16:00")
    print("3. 16:00 - 00:00")
    
    choice = input("Введите номер варианта времени: ")
    
    if choice == "1":
        return '00:00', '08:00'
    elif choice == "2":
        return '08:00', '16:00'
    elif choice == "3":
        return '16:00', '00:00'
    else:
        print("Некорректный выбор времени.")
        return None

def select_positions(conn):
    selected_positions = []
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM Positions;")
        positions = cursor.fetchall()

    if not positions:
        print("Нет доступных позиций в базе данных.")
        return []

    print("Доступные позиции:")
    for position in positions:
        print(f"{position[0]}. {position[1]}")

    while True:
        choice = input("Введите номер позиции (или 'q' для завершения): ")

        if choice.lower() == 'q':
            break

        try:
            position_id = int(choice)
            if any(position_id == pos[0] for pos in positions):
                selected_positions.append(position_id)
                print(f"Позиция {position_id} добавлена.")
            else:
                print("Некорректный выбор. Пожалуйста, введите корректный номер.")
        except ValueError:
            print("Некорректный ввод. Пожалуйста, введите номер позиции или 'q' для завершения.")

    if not selected_positions:
        print("Необходимо выбрать хотя бы одну позицию.")
        return select_positions(conn)

    return selected_positions

def add_employee(conn):
    global logged_in
    global current_user_id

    if not logged_in:
        print("Для добавления сотрудника необходимо войти в систему.")
        return

    if not is_admin(conn, current_user_id):
        print("У вас нет прав для добавления сотрудника.")
        return

    user_name = input("Введите имя пользователя, которого вы хотите назначить сотрудником: ")

    user_id = get_user_id_by_name(conn, user_name)

    if not user_id:
        print("Пользователь с указанным именем не существует.")
        return

    delete_client(conn, user_id)

    salary = input("Введите зарплату сотрудника: ")
    work_time = select_work_time()
    
    if not work_time:
        return
    
    positions = select_positions(conn)
    with conn.cursor() as cursor:
        try:
            cursor.execute("""
                INSERT INTO Employees (Salary, User_Id, Work_time_Id)
                VALUES (%s, %s, (SELECT Id FROM Work_time WHERE start_work = %s AND end_work = %s))
                RETURNING Id
            """, (salary, user_id, work_time[0], work_time[1]))

            employee_id = cursor.fetchone()[0]
            for position_name in positions:
                cursor.execute("""
                    INSERT INTO Positions_Employees (Position_Id, Employee_Id)
                    VALUES ((SELECT Id FROM Positions WHERE Id = %s), %s)
                """, (position_name, employee_id))
            
            cursor.execute("""
                UPDATE Users
                SET Role_Id = 3
                WHERE Id = %s
            """, (user_id,))

            conn.commit()
            print("Сотрудник успешно добавлен.")
        except Exception as e:
            conn.rollback()
            print(f"Ошибка при добавлении сотрудника: {e}")

def select_producer(conn):
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM Producers;")
        producers = cursor.fetchall()

    if not producers:
        print("Нет доступных производителей в базе данных.")
        return None

    while True:
        print("Доступные производители:")
        for producer in producers:
            print(f"{producer[0]}. {producer[1]} ({producer[2]})")

        choice = input("Введите номер производителя (или 'q' для завершения): ")

        if choice.lower() == 'q':
            return None

        try:
            producer_id = int(choice)
            if any(producer_id == prod[0] for prod in producers):
                return producer_id
            else:
                print("Некорректный выбор. Пожалуйста, введите корректный номер.")
        except ValueError:
            print("Некорректный ввод. Пожалуйста, введите номер производителя или 'q' для завершения.")

    return None

def add_producer(conn):
    global logged_in
    global current_user_id

    if not logged_in:
        print("Для добавления производителя необходимо войти в систему.")
        return

    if not is_admin(conn, current_user_id) and not is_employee(conn, current_user_id):
        print("У вас нет прав для добавления производителя.")
        return

    producer_name = input("Введите название производителя: ")
    producer_country = input("Введите страну производителя: ")

    with conn.cursor() as cursor:
        try:
            cursor.execute("""
                INSERT INTO Producers (Name, Country)
                VALUES (%s, %s)
            """, (producer_name, producer_country))

            conn.commit()
            print("Производитель успешно добавлен.")
        except Exception as e:
            conn.rollback()
            print(f"Ошибка при добавлении производителя: {e}")

def add_fruit(conn):
    global logged_in
    global current_user_id

    if not logged_in:
        print("Для добавления фрукта необходимо войти в систему.")
        return

    if not is_admin(conn, current_user_id) and not is_employee(conn, current_user_id):
        print("У вас нет прав для добавления фрукта.")
        return

    fruit_name = input("Введите название фрукта: ")
    creation_date = input("Введите дату создания фрукта (гггг-мм-дд): ")
    price = input("Введите цену фрукта: ")
    expiration_date = input("Введите срок годности фрукта (в днях): ")
    producer_id = select_producer(conn)

    with conn.cursor() as cursor:
        try:
            cursor.execute("CALL AddFruit(%s, %s, %s, %s, %s)",
                            (fruit_name, creation_date, price, expiration_date, producer_id))

            conn.commit()
            print("Фрукт успешно добавлен.")
        except Exception as e:
            conn.rollback()
            print(f"Ошибка при добавлении фрукта: {e}")

def update_fruit_price_by_percentage(conn):
    if not logged_in:
        print("\nДля добавления фрукта необходимо войти в систему.")
        return
    
    global current_user_id

    if not is_admin(conn, current_user_id):
        print("У вас нет прав для обновления цены фрукта.")
        return

    fruit_name = input("Введите название фрукта: ")
   
    with conn.cursor() as cursor1:
            cursor1.execute("""
                SELECT fruits.Id 
                FROM fruits
                WHERE fruits.Name = %s""", (f'{fruit_name}',))

            fruit = cursor1.fetchone()
    if not fruit:
        print(f"Фрукт {fruit_name} не найден")
        return
    
    new_price = input("Введите новую цену фрукта: ")
    try:
        with conn.cursor() as cursor:
            cursor.execute("CALL UpdateFruitPriceByPercentage(%s, %s)",
                            (fruit[0], new_price))
            conn.commit()
            print(f"Цена для фрукта {fruit_name} изменена на {new_price}.")
    except psycopg2.Error as e:
        conn.rollback()
        print(f"Ошибка при выполнении процедуры: {e}")

def delete_low_rated_reviews_for_all_fruits(conn):

    if not logged_in:
        print("\nДля добавления фрукта необходимо войти в систему.")
        return
    
    global current_user_id

    if not is_admin(conn, current_user_id):
        print("У вас нет прав для удаления отзывов.")
        return

    try:
        with conn.cursor() as cursor:
            cursor.execute('CALL DeleteLowRatedReviewsForAllFruits()')
            conn.commit()
            print("Низкооцененные отзывы успешно удалены.")
    except psycopg2.Error as e:
        conn.rollback()
        print(f"Ошибка при выполнении процедуры: {e}")

def delete_fruit(conn):
    global logged_in
    global current_user_id

    if not logged_in:
        print("Для удаления фрукта необходимо войти в систему.")
        return

    if not is_admin(conn, current_user_id) and not is_employee(conn, current_user_id):
        print("У вас нет прав для удаления фрукта.")
        return

    fruit_name = input("Введите название фрукта: ")
    with conn.cursor() as cursor1:
            cursor1.execute("SELECT * FROM Fruits WHERE LOWER(Name) = LOWER(%s);", (fruit_name,))
            fruit = cursor1.fetchone()
            if not fruit:
                print(f"Фрукт '{fruit_name}' не найден.")
                return
    with conn.cursor() as cursor:
        try:
            cursor.execute("DELETE FROM Fruits WHERE LOWER(Name) = LOWER(%s);", (fruit_name,))
            conn.commit()
            print(f"Фрукт '{fruit_name}' успешно удален.")
        except psycopg2.Error as e:
            conn.rollback()
            print(f"Ошибка при удалении фрукта: {e}")


def register_user(conn, first_name, last_name, phone, password, role_id, address):
    global logged_in
    global current_user_id
    with conn.cursor() as cursor:
        try:
            if len(first_name) < 1:
                raise ValueError("Имя должно содержать не менее 1 символа.")
            if len(last_name) < 1:
                raise ValueError("Фамилия должна содержать не менее 1 символа.")
            if not is_valid_phone(phone):
                raise ValueError("Некорректный формат телефона. Пример: +375291111111")
            if not is_valid_password(password):
                raise ValueError("Пароль должен содержать не менее 4 цифр.")

            cursor.execute("""
                INSERT INTO Users (First_Name, Last_Name, Phone, Password, Role_Id)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING Id
            """, (first_name, last_name, phone, password, role_id))
            user_id = cursor.fetchone()[0]
            conn.commit()
            cursor.execute("""
                INSERT INTO Clients (User_Id, Address)
                VALUES (%s, %s)
            """, (user_id, address))
            
            conn.commit()
            
            print("Пользователь успешно зарегистрирован!")

            login_user(conn, first_name, password)
            logged_in = True 
            current_user_id = user_id  
        except Exception as e:
            conn.rollback()
            print(f"Ошибка при регистрации пользователя: {e}")

def login_user(conn, first_name, password):
    global logged_in
    global current_user_id  
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT * FROM Users
            WHERE First_name = %s AND Password = %s
        """, (first_name, password))
        user = cursor.fetchone()
        if user:
            print(f"Добро пожаловать, {user[1]} {user[2]}!")
            logged_in = True
            current_user_id = user[0]  
        else:
            print("Неверный логин или пароль.")

def logout_user():
    global logged_in
    global current_user_id  
    print("Вы успешно вышли из аккаунта.")
    logged_in = False
    current_user_id = None  

def main():
    global logged_in
    while True:
        if not logged_in:
            print("\nВыберите действие:")
            print("1. Зарегистрироваться")
            print("2. Войти")
           
        else:
            print("\nВыберите действие:")
            print("1. Выход из аккаунта")
            print("2. История моих заказов")

        print("3. Список фруктов")
        print("4. Информация о фрукте и операции с товаром")
        print("5. Список сотрудников")
        print("6. Добавить сотрудника")
        print("7. Добавить производителя фрукта")
        print("8. Добавить фрукт")
        print("9. Удалить фрукт")
        print("10. Изменить цену продукта")
        print("11. Удалить все \"плохие\" отзывы")
        print("0. Выход из приложения")


        choice = input("\nВыберете операцию: ")

        if not logged_in:
            if choice == "1":
                first_name = input("Введите ваше имя: ")
                last_name = input("Введите вашу фамилию: ")
                phone = input("Введите ваш номер телефона: ")
                address = input("Введите адрес: ")
                password = getpass.getpass("Введите ваш пароль: ")
                role_id = 2
                register_user(conn, first_name, last_name, phone, password, role_id, address)
            elif choice == "2":
                phone = input("Введите логин: ")
                password = getpass.getpass("Введите пароль: ")
                login_user(conn, phone, password)
        elif logged_in:
            if choice == "1":
                logout_user()
            elif choice == "2":
                show_history(conn)

        if choice == "3":
            select_fruits()
        elif choice == "4":
            fruit_name = input("Введите наименование фрукта: ")
            is_valid_fruit = get_fruit_info(conn, fruit_name)
            if is_valid_fruit:
                print("1. Отзывы о фрукте")
                print("2. Оставить отзыв")
                print("3. Купить")
                fruit_detail_choice = input("\nВыберете операцию: ")

                if fruit_detail_choice == "1":
                    get_reviews_for_fruit(fruit_name)
                elif fruit_detail_choice == "2":
                    leave_review(conn, fruit_name)
                elif fruit_detail_choice == "3":
                    make_order(conn, fruit_name)            
                else: 
                    break

        elif choice == "5":
            view_employees()
        elif choice == "6":
            add_employee(conn)
        elif choice == "7":
            add_producer(conn)
        elif choice == "8":
            add_fruit(conn)
        elif choice == "9":
            delete_fruit(conn)
        elif choice == "10":
            update_fruit_price_by_percentage(conn)
        elif choice == "11":
            delete_low_rated_reviews_for_all_fruits(conn)
        elif choice == "0":
            break
        elif choice != "1" and choice != "2":
            print("Некорректный выбор. Попробуйте снова.")

if __name__ == "__main__":
    try:
        main()
    finally:
        conn.close()
