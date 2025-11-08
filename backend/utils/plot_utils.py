import os
import matplotlib.pyplot as plt

def plot_training_metrics(train_losses, val_losses, val_accuracies, save_dir="training-metrics", filename="training_metrics.png"):
    """
    Plot training & validation loss and validation accuracy.

    Args:
        train_losses (list[float]): Training loss per epoch
        val_losses (list[float]): Validation loss per epoch
        val_accuracies (list[float]): Validation accuracy (%) per epoch
        save_dir (str): Directory to save plots
        filename (str): Plot filename
    """

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))

    # Top subplot: train & validation loss
    ax1.plot(train_losses, label="Ошибка обучения", marker='o')
    ax1.plot(val_losses, label="Ошибка валидации", marker='o')
    ax1.set_xlabel("Эпоха")
    ax1.set_ylabel("Ошибка")
    ax1.set_title("Ошибка на обучении и валидации")
    ax1.legend()
    ax1.grid(True)

    # Bottom subplot: validation accuracy
    ax2.plot(val_accuracies, label="Точность валидации", color='green', marker='o')
    ax2.set_xlabel("Эпоха")
    ax2.set_ylabel("Точность (%)")
    ax2.set_title("Точность на валидации")
    ax2.legend()
    ax2.grid(True)

    plt.tight_layout()

    os.makedirs(save_dir, exist_ok=True)
    plot_path = os.path.join(save_dir, filename)
    plt.savefig(plot_path)

    print(f"[INFO] Training plots saved to {plot_path}")

    plt.show()
