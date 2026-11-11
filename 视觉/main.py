import time, os, sys
from media.sensor import *
from media.display import *
from media.media import *
from machine import Pin,PWM
from machine import FPIOA
from machine import UART

thresholds = [(30, 59, 21, 60, -3, 57), # 红色
              (5, 25, -7, 7, -6, 11), # 黑色
              (0, 80, 0, 90, -128, -20)] # 蓝色

try:
    sensor = Sensor(width=640, height=480)
    sensor.reset()
    sensor.set_framesize(Sensor.VGA)
    sensor.set_pixformat(Sensor.RGB565)

    Display.init(Display.ST7701, width=640, height=480, to_ide=True)
    MediaManager.init()
    sensor.run()
    clock = time.clock()

    fpioa = FPIOA()
    uart1 = UART(UART.UART1, baudrate=115200, bits=UART.EIGHTBITS, parity=UART.PARITY_NONE, stop=UART.STOPBITS_ONE)
    uart2 = UART(UART.UART2, baudrate=115200, bits=UART.EIGHTBITS, parity=UART.PARITY_NONE, stop=UART.STOPBITS_ONE)

    fpioa.set_function(35,FPIOA.GPIO35)
    fpioa.set_function(34,FPIOA.GPIO34)

    key0 = Pin(34, Pin.IN, pull=Pin.PULL_UP, drive=7)
    key1 = Pin(35, Pin.IN, pull=Pin.PULL_UP, drive=7)

    key1_long_time_press = 0
    # 保存锁定以后左上角的坐标
    boards_const = []
    stones_const = []

    # 按键检测相关变量
    key1_last_state = 1
    key1_press_start_time = 0
    key1_long_press_detected = 0

    # 按键选择数字的相关变量
    key1_times = 0
    key0_times = 0
    key1_last_state_num = 1
    key0_last_state_num = 1
    key1_press_start_time_num = 0
    key0_press_start_time_num = 0

    while True:
        os.exitpoint()
        clock.tick()
        img = sensor.snapshot()

        # 获取当前时间
        current_time = time.ticks_ms()

        # ===== 非阻塞按键检测 =====
        key1_current_state = key1.value()

        # 检测按键按下（下降沿）
        if key1_current_state == 0 and key1_last_state == 1:
            key1_press_start_time = current_time
            print("按键按下")

        # 检测按键释放（上升沿）
        elif key1_current_state == 1 and key1_last_state == 0:
            press_duration = current_time - key1_press_start_time
            print(f"按键释放，持续时间: {press_duration}ms")

            # 如果按下时间超过2000ms，触发长按
            if press_duration >= 2000:
                key1_long_press_detected = 1

        # 更新按键状态
        key1_last_state = key1_current_state

        # 如果检测到长按，锁定状态
        if key1_long_press_detected:
            key1_long_time_press = 1
            key1_long_press_detected = 0  # 重置检测标志
            print("坐标已锁定!")

        # ===== 根据锁定状态处理图像 =====
        boards = []
        stones = []

        # 显示锁定状态
        if key1_long_time_press:
            img.draw_string(10, 10, "LOCKED", scale=3, color=(255, 0, 0))
        else:
            img.draw_string(10, 10, "UNLOCKED", scale=3, color=(0, 255, 0))

        # 显示按键状态
        key_state = "PRESSED" if key1_current_state == 0 else "RELEASED"
        img.draw_string(10, 40, f"Key: {key_state}", scale=2, color=(255, 255, 0))

        # 如果未锁定，实时检测和保存数据
        if not key1_long_time_press:
            blobs_board = img.find_blobs([thresholds[0]],
                                        pixels_threshold=200,
                                        area_threshold=1000)

            blobs_stones = img.find_blobs([thresholds[1]],pixels_threshold = 200,area_threshold = 700,roi = (10,40,330,480))

            # 处理黑色棋子
            if len(blobs_stones) >= 9:
                # 只取前9个色块
                blobs = blobs_stones[:9]

                # 按y坐标排序（从上到下）
                blobs_sorted_by_y = sorted(blobs, key=lambda b: b[6])

                # 分成三行
                rows = []
                for i in range(0, 9, 3):
                    row = sorted(blobs_sorted_by_y[i:i+3], key=lambda b: b[5])  # 按x坐标排序（从左到右）
                    rows.extend(row)  # 展平列表

                # 清空并重新保存排序后的数据
                stones_const.clear()
                blob_num = 1

                for blob in rows:
                    x, y = blob[5], blob[6]
                    stones.append([x, y])

                    # 保存完整数据到stones_const
                    stones_const.append([blob[0], blob[1], blob[2], blob[3], blob[5], blob[6]])

                    # 绘制矩形和十字
                    img.draw_rectangle(blob[0], blob[1], blob[2], blob[3],
                                     color=(0, 0, 255), thickness=4)
                    img.draw_cross(blob[5], blob[6], size=5, thickness=1)

                    # 显示编号
                    img.draw_string(x, y, f"{blob_num}",
                                  scale=4, color=(0, 255, 0))
                    blob_num += 1
            else:
                # 显示找到的色块数量
                img.draw_string(10, 70, f"Stones: {len(blobs_stones)}/9",
                              scale=2, color=(255, 255, 255))

            # 处理红色棋盘
            if len(blobs_board) >= 9:
                # 只取前9个色块
                blobs = blobs_board[:9]

                # 按y坐标排序（从上到下）
                blobs_sorted_by_y = sorted(blobs, key=lambda b: b[6])

                # 分成三行
                rows = []
                for i in range(0, 9, 3):
                    row = sorted(blobs_sorted_by_y[i:i+3], key=lambda b: b[5])  # 按x坐标排序（从左到右）
                    rows.extend(row)  # 展平列表

                # 清空并重新保存排序后的数据
                boards_const.clear()
                blob_num = 1

                for blob in rows:
                    x, y = blob[5], blob[6]
                    boards.append([x, y])

                    # 保存完整数据到boards_const
                    boards_const.append([blob[0], blob[1], blob[2], blob[3], blob[5], blob[6]])

                    # 绘制矩形和十字
                    img.draw_rectangle(blob[0], blob[1], blob[2], blob[3],
                                     color=(255, 0, 0), thickness=4)
                    img.draw_cross(blob[5], blob[6], size=5, thickness=1)

                    # 显示编号
                    img.draw_string(x, y, f"{blob_num}",
                                  scale=4, color=(0, 255, 0))
                    blob_num += 1
            else:
                # 显示找到的色块数量
                img.draw_string(10, 100, f"Boards: {len(blobs_board)}/9",
                              scale=2, color=(255, 255, 255))

        # 如果已锁定，绘制保存的数据
        else:
            # 绘制保存的棋盘数据
            for i, board_const in enumerate(boards_const):
                img.draw_rectangle(board_const[0], board_const[1], board_const[2], board_const[3],
                                 color=(255, 0, 0), thickness=4)
                img.draw_cross(board_const[4], board_const[5], size=5, thickness=1)
                # 显示编号
                img.draw_string(board_const[4], board_const[5], f"{i+1}",
                              scale=4, color=(0, 255, 0))

            # 绘制保存的棋子数据
            for i, stone_const in enumerate(stones_const):
                img.draw_rectangle(stone_const[0], stone_const[1], stone_const[2], stone_const[3],
                                 color=(0, 0, 255), thickness=4)
                img.draw_cross(stone_const[4], stone_const[5], size=5, thickness=1)
                # 显示编号
                img.draw_string(stone_const[4], stone_const[5], f"{i+1}",
                              scale=4, color=(0, 255, 0))
            # 检测输入按键是否已经按完
            if key1_times<=0:
                key1_press_start_time_num = time.ticks_ms()

            if not key1.value() and key1_last_state_num and time.ticks_ms() - key1_press_start_time_num<=2000:
                key1_times = key1_times+1
                key1_press_start_time_num = time.ticks_ms()

            if key1.value():
                key1_last_state_num = 1
            else:
                key1_last_state_num = 0

            if key0_times<=0:
                key0_press_start_time_num = time.ticks_ms()

            if not key0.value() and key0_last_state_num and time.ticks_ms() - key0_press_start_time_num<=2000:
                key0_times = key0_times+1
                key0_press_start_time_num = time.ticks_ms()

            if key0.value():
                key0_last_state_num = 1
            else:
                key0_last_state_num = 0

            if key0_times>9:
                key0_times = 1
            if key1_times>9:
                key1_times = 1

            # 串口发送数据
            if time.ticks_ms() - key0_press_start_time_num>2050:
                img.draw_string(400,10,f"uart1_puting",scale=2, color=(255, 255, 255))
                uart1.write(f"X{boards_const[key0_times-1][4]}Y{boards_const[key0_times-1][5]}E")

            if time.ticks_ms() - key1_press_start_time_num>2050:
                img.draw_string(460,10,f"uart2_puting",scale=2, color=(255, 255, 255))
                uart2.write(f"X{stones_const[key1_times-1][4]}Y{stones_const[key1_times-1][5]}E")

        # 显示FPS
        img.draw_string(10, 450, f"FPS: {clock.fps():.1f}",
                       scale=2, color=(255, 255, 255))

        # 显示保存的数据量
        img.draw_string(10, 430, f"保存: {len(boards_const)}板/{len(stones_const)}棋",
                       scale=2, color=(255, 255, 255))

        img.draw_string(400,450,f"key1:{key1_times},key0:{key0_times}",scale=2, color=(255, 255, 255))

        Display.show_image(img)
        print(f"FPS: {clock.fps()}, Locked: {key1_long_time_press}")
    time.sleep_ms(50)

except KeyboardInterrupt as e:
    print("user stop: ", e)
except BaseException as e:
    print(f"Exception {e}")
finally:
    if isinstance(sensor, Sensor):
        sensor.stop()
    Display.deinit()
    os.exitpoint(os.EXITPOINT_ENABLE_SLEEP)
    time.sleep_ms(100)
    MediaManager.deinit()
