# main.py - Startpunt van de game
import sys, traceback
import pygame
from opslaan import laad_save, sla_op, SCREEN_W, SCREEN_H, FPS
import geluid


def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("RPG - Kasteel & Bos")
    clock = pygame.time.Clock()

    # Geluid initialiseren
    geluid.init_geluid()

    save  = laad_save()
    scene = "hub"

    while True:
        if scene == "hub":
            from hub import HubScene
            resultaat = HubScene(screen, clock, save).run()
            if resultaat == "quit":
                break
            elif resultaat == "bos":
                scene = "bos"

        elif scene == "bos":
            from bos import BosScene
            resultaat, save = BosScene(screen, clock, save).run()
            sla_op(save)
            if resultaat == "quit":
                break
            elif resultaat == "hub":
                scene = "hub"

    pygame.quit()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("\n---- FOUTMELDING ----------------------------------------")
        traceback.print_exc()
        input("\nDruk op Enter om af te sluiten...")
        sys.exit()
