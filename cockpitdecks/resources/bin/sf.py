import time


def solari(display: str):
    LAST = 4
    SPEED = 0.1
    display = display.upper()
    screen = [" " for i in range(len(display))]
    j = 0
    for c in display:
        end = ord(c) + 1
        print(ord(c))
        for i in range(ord("0"), end):
            if (i > 57 and i < 65) or (i > 96):  # only keep number and letters
                continue
            screen[j] = chr(i)
            if d := (end - i) < 4:
                print("s", "".join(screen))
                time.sleep(SPEED)
                # time.sleep((LAST*SPEED) - SPEED * d)
            else:
                print("f", "".join(screen))
                time.sleep(SPEED)
        j = j + 1


solari("DZ12")
