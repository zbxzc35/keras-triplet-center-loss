from tensorflow.keras.layers import Input
import tensorflow as tf
from tensorflow.keras.models import Model
from load_mnist import load_mnist
from base_network import cnn
from triplet import generate_triplet, triplet_loss
from sklearn.preprocessing import LabelBinarizer
import numpy as np
import os

def train(outdir, batch_size, n_epochs, lr):

    outdir = outdir + "/center_loss/"

    if not os.path.isdir(outdir):
        os.makedirs(outdir)

    x_train, y_train, y_train_onehot, x_test, y_test, y_test_onehot = load_mnist()

    model_input = Input(shape=(28, 28, 1))

    softmax, pre_logits = cnn(model_input)

    x_train_flat = x_train.reshape(-1, 784)
    #x_test_flat = x_test.reshape(-1, 784)

    X_train, Y_train = generate_triplet(x_train_flat, y_train, ap_pairs=150, an_pairs=150)

    from tensorflow.keras.layers import concatenate, Lambda, Embedding
    import tensorflow.keras.backend as K

    target_input = Input((1,), name='target_input')

    center = Embedding(10, 32)(target_input)
    l2_loss = Lambda(lambda x: K.sum(K.square(x[0] - x[1][:, 0]), 1, keepdims=True), name='l2_loss_anchor')(
        [pre_logits, center])

    shared_model = tf.keras.models.Model(inputs=[model_input, target_input], outputs=[softmax, l2_loss, pre_logits])

    anchor_input = Input((28, 28, 1,), name='anchor_input')
    positive_input = Input((28, 28, 1,), name='positive_input')
    negative_input = Input((28, 28, 1,), name='negative_input')

    target_anchor_input = Input((1,), name="anchor_target_input")
    target_positive_input = Input((1,), name='target_positive_input')
    target_negative_input = Input((1,), name='target_negative_input')

    soft_anchor, l2_anchor, pre_logits_anchor = shared_model([anchor_input, target_anchor_input])
    soft_pos, l2_positive, pre_logits_pos = shared_model([positive_input, target_positive_input])
    soft_neg, l2_negative, pre_logits_neg = shared_model([negative_input, target_negative_input])

    merged_l2 = concatenate([l2_anchor, l2_positive, l2_negative], axis=-1, name="merged_l2")

    merged_soft = concatenate([soft_anchor, soft_pos, soft_neg], axis=-1, name='merged_soft')

    model = Model(inputs=[anchor_input, positive_input, negative_input, target_anchor_input, target_positive_input,
                          target_negative_input], outputs=[merged_soft, merged_l2])
    model.compile(loss=["categorical_crossentropy", lambda y_true, y_pred: y_pred],
                  optimizer=tf.keras.optimizers.Adam(lr=lr), metrics=["accuracy"],
                  )

    le = LabelBinarizer()

    Anchor = X_train[:, 0, :].reshape(-1, 28, 28, 1)
    Positive = X_train[:, 1, :].reshape(-1, 28, 28, 1)
    Negative = X_train[:, 2, :].reshape(-1, 28, 28, 1)

    Y_Anchor = le.fit_transform(Y_train[:, 0])
    Y_Positive = le.fit_transform(Y_train[:, 1])
    Y_Negative = le.fit_transform(Y_train[:, 2])

    target = np.concatenate((Y_Anchor, Y_Positive, Y_Negative), -1)

    model.fit([Anchor, Positive, Negative, Y_train[:, 0], Y_train[:, 1], Y_train[:, 2]], y=[target, target],
              batch_size=batch_size, epochs=n_epochs, validation_split=0.2)

    model.save("center_loss_model.h5")

    model = Model(inputs=[anchor_input, target_anchor_input], outputs=[soft_anchor, l2_anchor, pre_logits_anchor])
    model.load_weights("center_loss_model.h5")

    _, _, X_train_embed = model.predict([x_train[:512], y_train[:512]])
    _, _, X_test_embed = model.predict([x_test[:512], y_train[:512]])

    from TSNE_plot import tsne_plot

    tsne_plot(X_train_embed, y_train, X_test_embed, y_test, "center_loss")

