import random

def monty_hall_simulate(try_cnt, is_change_door):
    wins = 0

    for _ in range(try_cnt):
        # 승리하는 문 번호
        win_door = random.randint(0, 2)

        # 참가자 선택
        select_door = random.randint(0, 2)

        if win_door == select_door:
            # 승리하는 문을 선택한 경우
            unvail_door = random.choice([door for door in range(3) if door != select_door])
        else:
            # 승리하는 문을 선택하지 않은 경우
            unvail_door = [door for door in range(3) if door != select_door and door != win_door][0]

        if is_change_door:
            # 문을 바꾸는 경우
            select_door = [door for door in range(3) if door != select_door and door != unvail_door][0]

        if select_door == win_door:
            wins += 1

    return wins / try_cnt

if __name__ == '__main__':
    try_cnt = 1000000
    print(f'Change door: {monty_hall_simulate(try_cnt, True)}')
    print(f'Stay door: {monty_hall_simulate(try_cnt, False)}')
