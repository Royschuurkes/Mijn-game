# main.py - Entry point and scene manager
import pygame
from constants import load_save, save_game, SCREEN_W, SCREEN_H, FPS
import sound


def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("Het Bos")
    clock = pygame.time.Clock()

    sound.init_sound()

    save = load_save()
    scene = "hub"

    while True:
        if scene == "hub":
            from hub import HubScene
            result = HubScene(screen, clock, save).run()
        elif scene == "forest":
            from forest import ForestScene
            result = ForestScene(screen, clock, save).run()
        else:
            break

        if result == "quit":
            break
        elif result == "hub":
            save = load_save()
            scene = "hub"
        elif result == "forest":
            scene = "forest"
        else:
            break

    save_game(save)
    pygame.quit()


if __name__ == "__main__":
    main()