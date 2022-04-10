import random
import numpy as np
import time
import pygame

# constantes de simulation
width = 200
height = 100
immunized_probability = 0
sick_probability = 0.0005
death_probability = 0.05
spread_probability = 0.01
time_before_death = 20
time_before_recovery = 30
# constantes d'affichage
scale = 3
colors = [(0, 0, 0), (0, 255, 0), (255, 0, 0), (255, 0, 0), (0, 0, 255)]

class Person:
    def __init__(self, state):
        self.state = state
        self.duration = 0
    

def init():
    # retourne un tableau 2D pour stocker les valeurs
    # 0 = dead, 1 = normal, 2 = sick_dead, 3 = sick_recovery, 4 = immunized
    data = [[None] * width for _ in range(height)]
    sick_threshold = 1 - sick_probability
    sick_positions = []
    for i in range(height):
        for j in range(width):
            p = random.random()
            if p < immunized_probability:
                data[i][j] = Person(4)      
            elif p < sick_threshold:
                data[i][j] = Person(1)
            else:
                p = random.random()
                data[i][j] = Person(2 if p < death_probability else 3)
                data[i][j].duration = time_before_death if p < death_probability else time_before_recovery
                sick_positions.append((i, j))

    return data, sick_positions

        
def next_iteration(data, sick_list):
    new_sick_list = []
    for i, j in sick_list:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                x, y = i + dx, j + dy
                if x < 0 or x >= height or y < 0 or y >= width or data[x][y].state in (0, 2, 3, 4):
                    continue
    
                if random.random() < spread_probability:
                    p = random.random()
                    data[x][y].state = 2 if p < death_probability else 3
                    data[x][y].duration = time_before_death if p < death_probability else time_before_recovery
                    new_sick_list.append((x, y))
    
        data[i][j].duration -= 1
        if data[i][j].duration <= 0:
            data[i][j].state = 0 if data[i][j].state == 2 else 4
        else:
            new_sick_list.append((i, j))

    return new_sick_list

    
def generateImage(data):
    # les axes sont inverses
    img = np.empty((width, height, 3), dtype=np.int8)
    for i, row in enumerate(data):
        for j, v in enumerate(row):
            img[j, i] = colors[v.state]

    return img


def exec():
    data, sick_list = init()
    display = pygame.display.set_mode((scale * width, scale * height))
    pygame.display.set_caption("Iteration 0")
    img = pygame.surfarray.make_surface(generateImage(data))
    pygame.transform.scale(img, (scale * width, scale * height), display)
    pygame.display.flip()
    i = 1
    iteration_start = time.time()
    while sick_list:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.display.quit()
                pygame.quit()
                return
                
        sick_list = next_iteration(data, sick_list)
        pygame.pixelcopy.array_to_surface(img, generateImage(data))
        pygame.transform.scale(img, (scale * width, scale * height), display)
        pygame.display.flip()
        pygame.display.set_caption(f"Iteration {i}")
        i += 1

    iteration_end = time.time()
    print("end of simulation")
    print(f"done {i} iterations in {round(iteration_end - iteration_start, 3)} seconds")
    print(f"{round(i / (iteration_end - iteration_start), 1)} iterations/s in average") #, target was {speed} ({round(100 * (i / (iteration_end - iteration_start)) / speed, 2)}%)")
    print("sleep for 10 seconds before exiting script")
    time.sleep(10)
    pygame.display.quit()
    pygame.quit()


if __name__ == "__main__":
    exec()

