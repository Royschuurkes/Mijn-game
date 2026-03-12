# main.py - Entry point and scene manager
import pygame
from constants import load_save, save_game, SCREEN_W, SCREEN_H, FPS
import sound


def main():
    pygame.init()

    # FULLSCREEN | SCALED: pygame renders at SCREEN_W x SCREEN_H internally
    # and scales it to fill the monitor automatically, including mouse coordinates.
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), pygame.FULLSCREEN | pygame.SCALED)
    pygame.display.set_caption("The Forest")
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
