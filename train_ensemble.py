
import argparse
import os
import numpy as np
from models import train_ensemble
from data_ingestion import load_training_csv

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Train an ensemble from a canonical training CSV.')
    parser.add_argument('--csv', required=True, help='Path to training CSV file')
    parser.add_argument('--n-models', type=int, default=3, help='Number of ensemble members')
    parser.add_argument('--epochs', type=int, default=50, help='Epochs to train each model')
    parser.add_argument('--batch-size', type=int, default=32, help='Training batch size')
    parser.add_argument('--output-dir', default='saved_model/ensemble', help='Directory to save ensemble models')
    args = parser.parse_args()

    X_df, Y_df = load_training_csv(args.csv, allow_inputs_as_targets=False)
    X = X_df.values.astype(np.float32)
    Y = Y_df.values.astype(np.float32)

    mean = X.mean(axis=0)
    std = X.std(axis=0)
    std[std == 0] = 1.0
    Xs = (X - mean) / std

    os.makedirs(args.output_dir, exist_ok=True)
    paths = train_ensemble(Xs, Y, n_models=args.n_models, epochs=args.epochs, batch_size=args.batch_size, ensemble_dir=args.output_dir)
    print('Trained ensemble models:')
    for p in paths:
        print('-', p)
    os.makedirs('saved_model', exist_ok=True)
    np.savez(os.path.join('saved_model', 'scaler.npz'), mean=mean, std=std)
    print('Saved scaler to saved_model/scaler.npz')
