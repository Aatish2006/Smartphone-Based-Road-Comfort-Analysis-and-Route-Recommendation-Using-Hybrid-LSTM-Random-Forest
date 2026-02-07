"""
LSTM Encoder Training Module

Trains a temporal LSTM network to learn compact vibration embeddings
from multivariate accelerometer and gyroscope time series data.

The trained encoder outputs a fixed-dimensional embedding that captures
temporal dynamics of road surface vibrations.
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
import numpy as np
import yaml
from pathlib import Path
import logging
from typing import Tuple, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LSTMEncoder(nn.Module):
    """
    Bidirectional LSTM encoder for temporal vibration analysis.
    
    Input: [batch_size, sequence_length, num_features]
        - num_features = 6 (ax, ay, az, gx, gy, gz)
        - sequence_length = 300 samples (3 seconds at 100 Hz)
    
    Output: [batch_size, embedding_dim]
        - embedding_dim = 64 (compact temporal representation)
    """
    
    def __init__(self, 
                 input_features: int = 6,
                 num_layers: int = 2,
                 hidden_units: list = None,
                 embedding_dim: int = 64,
                 dropout: float = 0.2,
                 bidirectional: bool = True):
        super(LSTMEncoder, self).__init__()
        
        if hidden_units is None:
            hidden_units = [128, 64]
        
        self.input_features = input_features
        self.embedding_dim = embedding_dim
        self.bidirectional = bidirectional
        
        # Build LSTM layers
        self.lstm_layers = nn.ModuleList()
        
        input_dim = input_features
        for i in range(num_layers):
            lstm = nn.LSTM(
                input_size=input_dim,
                hidden_size=hidden_units[i],
                batch_first=True,
                dropout=dropout if i < num_layers - 1 else 0,
                bidirectional=bidirectional
            )
            self.lstm_layers.append(lstm)
            # Next layer's input is current hidden size (doubled if bidirectional)
            input_dim = hidden_units[i] * (2 if bidirectional else 1)
        
        # Output projection: lstm_output -> embedding_dim
        self.projection = nn.Linear(input_dim, embedding_dim)
        self.dropout = nn.Dropout(dropout)
        self.relu = nn.ReLU()
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.
        
        Args:
            x: [batch_size, sequence_length, input_features]
        
        Returns:
            embedding: [batch_size, embedding_dim]
        """
        for lstm in self.lstm_layers:
            x, _ = lstm(x)
        
        # Take last output (temporal pattern summary)
        x = x[:, -1, :]  # [batch_size, lstm_hidden_dim]
        
        # Project to embedding
        x = self.dropout(x)
        embedding = self.projection(x)  # [batch_size, embedding_dim]
        embedding = self.relu(embedding)
        
        return embedding


class LSTMEncoderWithClassifier(nn.Module):
    """
    LSTM encoder + classification head for supervised learning.
    After training, we extract the encoder portion for inference.
    """
    
    def __init__(self, encoder: LSTMEncoder, num_classes: int = 2):
        super(LSTMEncoderWithClassifier, self).__init__()
        self.encoder = encoder
        self.classifier = nn.Sequential(
            nn.Linear(encoder.embedding_dim, 32),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(32, num_classes)
        )
    
    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Forward pass returning both embedding and classification output.
        
        Args:
            x: [batch_size, sequence_length, input_features]
        
        Returns:
            embedding: [batch_size, embedding_dim]
            logits: [batch_size, num_classes]
        """
        embedding = self.encoder(x)
        logits = self.classifier(embedding)
        return embedding, logits


def load_config(config_path: str = "../config/model_config.yaml") -> Dict[str, Any]:
    """Load model configuration from YAML."""
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    return config


def train_lstm_encoder(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    config: Dict[str, Any],
    device: str = "cuda" if torch.cuda.is_available() else "cpu",
    output_dir: str = "./models"
) -> LSTMEncoder:
    """
    Train LSTM encoder with classification head.
    
    Args:
        X_train: [num_samples, sequence_length, num_features]
        y_train: [num_samples] class labels (0=normal, 1=pothole)
        X_val: validation data
        y_val: validation labels
        config: model configuration dict
        device: torch device
        output_dir: directory to save checkpoints
    
    Returns:
        Trained LSTMEncoder
    """
    
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Convert to torch tensors
    X_train_t = torch.FloatTensor(X_train).to(device)
    y_train_t = torch.LongTensor(y_train).to(device)
    X_val_t = torch.FloatTensor(X_val).to(device)
    y_val_t = torch.LongTensor(y_val).to(device)
    
    # Create datasets and loaders
    train_dataset = TensorDataset(X_train_t, y_train_t)
    val_dataset = TensorDataset(X_val_t, y_val_t)
    
    train_loader = DataLoader(
        train_dataset,
        batch_size=config['lstm']['batch_size'],
        shuffle=True
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=config['lstm']['batch_size'],
        shuffle=False
    )
    
    # Initialize model
    lstm_cfg = config['lstm']
    encoder = LSTMEncoder(
        input_features=lstm_cfg['input_features'],
        num_layers=lstm_cfg['num_layers'],
        hidden_units=lstm_cfg['hidden_units'],
        embedding_dim=lstm_cfg['embedding_dim'],
        dropout=lstm_cfg['dropout_rate']
    ).to(device)
    
    model = LSTMEncoderWithClassifier(encoder, num_classes=2).to(device)
    
    # Optimizer and loss
    optimizer = optim.Adam(
        model.parameters(),
        lr=lstm_cfg['learning_rate'],
        weight_decay=lstm_cfg['weight_decay']
    )
    criterion = nn.CrossEntropyLoss()
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode='min', factor=0.5, patience=5, verbose=True
    )
    
    best_val_loss = float('inf')
    patience_counter = 0
    
    logger.info(f"Training LSTM on {device} for {lstm_cfg['epochs']} epochs...")
    
    # Training loop
    for epoch in range(lstm_cfg['epochs']):
        # Train
        model.train()
        train_loss = 0.0
        for X_batch, y_batch in train_loader:
            optimizer.zero_grad()
            _, logits = model(X_batch)
            loss = criterion(logits, y_batch)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            train_loss += loss.item()
        
        train_loss /= len(train_loader)
        
        # Validate
        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for X_batch, y_batch in val_loader:
                _, logits = model(X_batch)
                loss = criterion(logits, y_batch)
                val_loss += loss.item()
        
        val_loss /= len(val_loader)
        
        if (epoch + 1) % 10 == 0:
            logger.info(f"Epoch {epoch+1}/{lstm_cfg['epochs']}: "
                        f"train_loss={train_loss:.4f}, val_loss={val_loss:.4f}")
        
        scheduler.step(val_loss)
        
        # Early stopping
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
            torch.save(
                encoder.state_dict(),
                Path(output_dir) / "lstm_encoder_best.pt"
            )
        else:
            patience_counter += 1
            if patience_counter >= lstm_cfg['early_stopping_patience']:
                logger.info(f"Early stopping at epoch {epoch+1}")
                break
    
    # Load best model
    encoder.load_state_dict(torch.load(Path(output_dir) / "lstm_encoder_best.pt"))
    logger.info(f"Best model saved to {output_dir}/lstm_encoder_best.pt")
    
    return encoder


def extract_embeddings(
    encoder: LSTMEncoder,
    X: np.ndarray,
    device: str = "cuda" if torch.cuda.is_available() else "cpu",
    batch_size: int = 64
) -> np.ndarray:
    """
    Extract embeddings using trained encoder.
    
    Args:
        encoder: Trained LSTMEncoder
        X: [num_samples, sequence_length, num_features]
        device: torch device
        batch_size: batch size for extraction
    
    Returns:
        embeddings: [num_samples, embedding_dim]
    """
    encoder.eval()
    encoder = encoder.to(device)
    
    embeddings = []
    with torch.no_grad():
        for i in range(0, len(X), batch_size):
            X_batch = torch.FloatTensor(X[i:i+batch_size]).to(device)
            emb = encoder(X_batch).cpu().numpy()
            embeddings.append(emb)
    
    embeddings = np.vstack(embeddings)
    return embeddings


if __name__ == "__main__":
    # Example usage (requires actual training data)
    config = load_config()
    
    logger.info("LSTM Encoder Training Module")
    logger.info(f"Config loaded: {config['lstm']}")
    logger.info("To train, call train_lstm_encoder() with your dataset.")
