
import argparse
import os
from training_pipeline import train_base_model, train_ensemble_from_csv

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--csv', required=True, help='Canonical training CSV')
    parser.add_argument('--model-dir', default='saved_model')
    parser.add_argument('--ensemble-dir', default='saved_model/ensemble')
    parser.add_argument('--epochs', type=int, default=100)
    parser.add_argument('--ensemble-epochs', type=int, default=50)
    parser.add_argument('--batch-size', type=int, default=32)
    parser.add_argument('--n-models', type=int, default=3)
    args = parser.parse_args()

    os.makedirs(args.model_dir, exist_ok=True)
    os.makedirs(args.ensemble_dir, exist_ok=True)

    print('Training base model...')
    try:
        metrics = train_base_model(args.csv, args.model_dir, epochs=args.epochs, batch_size=args.batch_size, validation_split=0.15)
        print('Base training metrics:', metrics)
    except Exception as e:
        print('Base training failed:', e)

    print('Training ensemble...')
    try:
        paths = train_ensemble_from_csv(args.csv, args.ensemble_dir, n_models=args.n_models, epochs=args.ensemble_epochs, batch_size=args.batch_size)
        print('Ensemble models:', paths)
    except Exception as e:
        print('Ensemble training failed:', e)

if __name__ == '__main__':
    main()
